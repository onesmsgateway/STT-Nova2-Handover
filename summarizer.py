import re
import asyncio
import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from typing import Optional
import os
from config import MAX_WORDS, GOOGLE_AI_MODEL, GOOGLE_API_KEYS, DEBUG_MODE
from key_manager import BaseAPIKeyManager
logger = logging.getLogger(__name__)

class GoogleAPIKeyManager(BaseAPIKeyManager):

    def rotate_to_next_key(self) -> str:
        return self.rotate_key()

def summarize_transcript(text: str, max_words: int=MAX_WORDS) -> str:
    if not text or not text.strip():
        return 'N/A'
    raw = text.strip()
    if len(raw) < 10:
        return 'N/A'
    sentences = re.split('(?<=[\\.!?])\\s+|\\n+', raw)
    priority_keywords = ['đặt', 'xác nhận', 'thanh toán', 'thời gian', 'địa chỉ', 'liên hệ', 'hỗ trợ', 'yêu cầu', 'khách', 'nhân viên', 'giao', 'đơn', 'món', 'bàn']
    selected = []
    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        lower = s_clean.lower()
        if any((k in lower for k in priority_keywords)):
            selected.append(s_clean)
    if len(selected) < 3:
        for s in sentences:
            s_clean = s.strip()
            if s_clean and s_clean not in selected:
                selected.append(s_clean)
            if len(selected) >= 5:
                break
    summary_text = ' '.join(selected) if selected else raw
    if len(summary_text.strip()) < 10:
        return 'N/A'
    words = summary_text.split()
    if len(words) > max_words:
        words = words[:max_words]
        summary_text = ' '.join(words).rstrip(',;') + '...'
    return summary_text

async def summarize_with_google_ai(api_key: str, text: str, max_words: int=MAX_WORDS, key_manager: GoogleAPIKeyManager=None) -> Optional[str]:
    try:
        if not text or not text.strip():
            if DEBUG_MODE:
                logger.info('⚠️ Transcript trống - Google AI trả về N/A')
            return 'N/A'
        current_api_key = api_key
        if key_manager:
            current_api_key = key_manager.get_current_key()
            if DEBUG_MODE:
                logger.info(f'🔑 Sử dụng {key_manager.get_key_info()}')
        genai.configure(api_key=current_api_key)
        model = genai.GenerativeModel(model_name=GOOGLE_AI_MODEL, generation_config={'temperature': 0.3, 'max_output_tokens': 1024})
        prompt = f'\nTôi có bản ghi chép cuộc hội thoại giữa nhân viên tổng đài và khách hàng bằng tiếng Việt dưới đây:\n\nTRANSCRIPT:\n{text}\n\nQUAN TRỌNG: \n- Nếu transcript trên TRỐNG hoặc chỉ có khoảng trắng, hãy trả về chính xác: "N/A"\n- Nếu transcript không có nội dung hội thoại thực sự, hãy trả về chính xác: "N/A"\n- CHỈ tóm tắt khi có nội dung hội thoại thực sự\n\nYêu cầu tóm tắt (chỉ khi có nội dung):\n- Tóm tắt ngắn gọn, dễ hiểu\n- Giữ lại thông tin quan trọng như thời gian, địa điểm, số lượng, tên người, số điện thoại, số nhà, tên đường\n- Tối đa {max_words} từ\n- Viết bằng tiếng Việt có dấu\n- Tập trung vào thông tin quan trọng nhất\n- Vấn đề khách hàng gặp phải, Kết quả cuối cùng là gì\n- Giải pháp nhân viên đã đề xuất\n- Xuống dòng, Gạch đầu dòng rõ ràng các ý\n\nTRẢ LỜI:\n'
        try:
            response = await asyncio.wait_for(model.generate_content_async(prompt), timeout=30.0)
        except asyncio.TimeoutError:
            if DEBUG_MODE:
                logger.info('⏰ Google AI Summarization timeout (30s) - chuyển sang thuật toán')
            return None
        if response and response.text:
            summary = response.text.strip()
            summary = summary.replace('Tóm tắt:', '').replace('Tóm tắt', '').strip()
            summary = summary.replace(f'({max_words} từ tối đa):', '').strip()
            words = summary.split()
            if len(words) > max_words:
                words = words[:max_words]
                summary = ' '.join(words).rstrip(',;') + '...'
            return summary
        else:
            if DEBUG_MODE:
                logger.info('⚠️ Google AI không trả về kết quả')
            return None
    except Exception as e:
        error_msg = str(e)
        if DEBUG_MODE:
            logger.info(f'❌ Lỗi khi gọi Google AI summarization: {error_msg}')
        if key_manager and ('quota' in error_msg.lower() or '429' in error_msg or 'resource_exhausted' in error_msg.lower()):
            if DEBUG_MODE:
                logger.info(f'🔄 Google AI quota/rate limit detected, rotating API key...')
            try:
                next_key = key_manager.rotate_to_next_key()
                if DEBUG_MODE:
                    logger.info(f'🔑 Google AI: Rotated to {key_manager.get_key_info()}')
                genai.configure(api_key=next_key)
                retry_model = genai.GenerativeModel(model_name=GOOGLE_AI_MODEL, generation_config={'temperature': 0.3, 'max_output_tokens': 1024})
                try:
                    response = await asyncio.wait_for(retry_model.generate_content_async(prompt), timeout=30.0)
                except asyncio.TimeoutError:
                    if DEBUG_MODE:
                        logger.info('⏰ Google AI Summarization retry timeout (30s)')
                    return None
                if response and response.text:
                    summary = response.text.strip()
                    summary = summary.replace('Tóm tắt:', '').replace('Tóm tắt', '').strip()
                    summary = summary.replace(f'({max_words} từ tối đa):', '').strip()
                    words = summary.split()
                    if len(words) > max_words:
                        words = words[:max_words]
                        summary = ' '.join(words).rstrip(',;') + '...'
                    if DEBUG_MODE:
                        logger.info(f'✅ Google AI retry successful with {key_manager.get_key_info()}')
                    return summary
                else:
                    if DEBUG_MODE:
                        logger.info('⚠️ Google AI không trả về kết quả sau khi rotate')
                    return None
            except Exception as retry_error:
                if DEBUG_MODE:
                    logger.info(f'❌ Google AI retry failed with new key: {retry_error}')
                return None
        return None

def get_summary_method(audio_file_path: str, google_api_key: str=None) -> str:
    if google_api_key and google_api_key != 'YOUR_GOOGLE_API_KEY' and (google_api_key != '********') and (len(google_api_key) > 10):
        return 'google_ai'
    else:
        return 'algorithm'