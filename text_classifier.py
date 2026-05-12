import re
import asyncio
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from typing import Optional, Dict, List, Tuple
import logging
from config import GOOGLE_AI_MODEL, GOOGLE_API_KEYS, DEBUG_MODE
from key_manager import BaseAPIKeyManager
logger = logging.getLogger(__name__)

class GoogleAPIKeyManager(BaseAPIKeyManager):

    def rotate_to_next_key(self) -> str:
        return self.rotate_key()

class TextClassifier:

    def __init__(self):
        self.negative_keywords = {'cờ_bạc': ['tài xỉu', 'đá gà', 'xóc đĩa', 'cá độ bóng đá', 'lô đề', 'best', 'cược', 'một ăn', 'cửa trên', 'cửa dưới', 'cửa tài', 'cửa xỉu', 'tài xỉu online', 'đánh bạc', 'cờ bạc', 'casino', 'poker', 'blackjack', 'roulette', 'số đề', 'lô tô', 'vé số', 'xổ số', 'keno', 'bingo', 'slot machine', 'bet', 'betting', 'gambling', 'wager', 'stake', 'odds', 'jackpot'], 'mại_dâm': ['gái gọi', 'đi khách', 'tàu nhanh', 'massage', 'em út', 'em đào', 'mấy đào', 'đá phò', 'phó đà', 'bán dâm', 'mại dâm', 'gái điếm', 'escort', 'prostitute', 'call girl', 'sex worker', 'brothel', 'massage parlor', 'red light', 'night club', 'bar girl', 'em gái', 'cô gái', 'phục vụ', 'dịch vụ đặc biệt', 'massage đặc biệt'], 'phản_động': ['chống đảng', 'chống nhà nước', 'lật đổ', 'cách mạng', 'biểu tình', 'đảo chính', 'khủng bố', 'bạo động', 'nổi loạn', 'chống chính quyền', 'tuyên truyền', 'tuyên truyền chống đối', 'tuyên truyền phản động', 'tổ chức bất hợp pháp', 'hoạt động bất hợp pháp', 'âm mưu', 'chống phá', 'phá hoại', 'gây rối', 'kích động', 'xúi giục']}
        self.regex_patterns = self._build_regex_patterns()
        self.prompts = self._build_prompts()

    def _build_regex_patterns(self) -> Dict[str, List[re.Pattern]]:
        patterns = {}
        for category, keywords in self.negative_keywords.items():
            patterns[category] = []
            for keyword in keywords:
                pattern = re.compile('\\b' + re.escape(keyword.lower()) + '\\b', re.IGNORECASE | re.UNICODE)
                patterns[category].append(pattern)
        return patterns

    def _build_prompts(self) -> Dict[str, str]:
        return {'zero_shot': '\nBạn là một hệ thống phân loại nội dung chuyên nghiệp. Nhiệm vụ của bạn là phân loại đoạn hội thoại sau thành một trong các nhóm sau:\n\n1. "cờ_bạc" - Nội dung liên quan đến cờ bạc, đánh bạc, cá độ, lô đề\n2. "mại_dâm" - Nội dung liên quan đến mại dâm, gái gọi, dịch vụ tình dục\n3. "phản_động" - Nội dung chống đối chính quyền, phản động, khủng bố\n4. "bình_thường" - Nội dung bình thường, không vi phạm\n\nĐoạn hội thoại cần phân loại:\n"{text}"\n\nYêu cầu:\n- Chỉ trả về một trong 4 nhãn trên (cờ_bạc, mại_dâm, phản_động, bình_thường)\n- Không giải thích, không thêm text khác\n- Phân loại chính xác dựa trên nội dung thực tế\n- Nếu không thể phân loại được nội dung (quá ngắn, không rõ ràng, không đủ thông tin) thì trả về "N/A"\n- Nếu không chắc chắn, chọn "bình_thường"\n\nKết quả phân loại:\n', 'few_shot': '\nBạn là một hệ thống phân loại nội dung chuyên nghiệp. Dưới đây là một số ví dụ phân loại:\n\nVí dụ 1: "Tôi muốn đặt cửa tài cho trận đấu tối nay" → cờ_bạc\nVí dụ 2: "Có gái gọi không?" → mại_dâm  \nVí dụ 3: "Chúng ta cần lật đổ chính quyền" → phản_động\nVí dụ 4: "Tôi muốn đặt bàn cho 2 người" → bình_thường\nVí dụ 5: "Massage đặc biệt có không?" → mại_dâm\nVí dụ 6: "Tôi cần hỗ trợ kỹ thuật" → bình_thường\nVí dụ 7: "Xin chào" → N/A\nVí dụ 8: "Cảm ơn" → N/A\n\nDựa vào các ví dụ trên, hãy phân loại đoạn hội thoại sau:\n"{text}"\n\nYêu cầu:\n- Chỉ trả về một trong 5 nhãn: cờ_bạc, mại_dâm, phản_động, bình_thường, N/A\n- Không giải thích, không thêm text khác\n- Phân loại chính xác dựa trên nội dung và ví dụ\n- Nếu không thể phân loại được nội dung (quá ngắn, không rõ ràng, không đủ thông tin) thì trả về "N/A"\n\nKết quả phân loại:\n'}

    def classify_with_regex(self, text: str) -> Tuple[str, List[str]]:
        if not text or not text.strip():
            return ('bình_thường', [])
        text_lower = text.lower()
        matched_keywords = []
        category_scores = {}
        for category, patterns in self.regex_patterns.items():
            category_matches = []
            for pattern in patterns:
                matches = pattern.findall(text_lower)
                if matches:
                    category_matches.extend(matches)
            if category_matches:
                category_scores[category] = len(category_matches)
                matched_keywords.extend(category_matches)
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            if DEBUG_MODE:
                logger.info(f'🔍 Regex classification: {best_category} (matches: {category_scores[best_category]})')
            return (best_category, matched_keywords)
        if DEBUG_MODE:
            logger.info('🔍 Regex classification: bình_thường (no negative keywords found)')
        return ('bình_thường', [])

    async def classify_with_ai(self, text: str, api_key: str, use_few_shot: bool=False, key_manager: GoogleAPIKeyManager=None) -> Optional[str]:
        try:
            current_api_key = api_key
            if key_manager:
                current_api_key = key_manager.get_current_key()
                if DEBUG_MODE:
                    logger.info(f'🔑 Text Classifier sử dụng {key_manager.get_key_info()}')
            genai.configure(api_key=current_api_key)
            model = genai.GenerativeModel(model_name=GOOGLE_AI_MODEL)
            prompt_template = self.prompts['few_shot'] if use_few_shot else self.prompts['zero_shot']
            prompt = prompt_template.format(text=text)
            if DEBUG_MODE:
                logger.info(f"🤖 AI Classification: {('Few-Shot' if use_few_shot else 'Zero-Shot')} mode")
            try:
                response = await asyncio.wait_for(model.generate_content_async(prompt), timeout=30.0)
            except asyncio.TimeoutError:
                if DEBUG_MODE:
                    logger.warning('⏰ Google AI Classification timeout (30s) - trả về bình_thường')
                return 'bình_thường'
            if response and response.text:
                result = response.text.strip().lower()
                valid_categories = ['cờ_bạc', 'mại_dâm', 'phản_động', 'bình_thường', 'n/a']
                for category in valid_categories:
                    if category in result:
                        if DEBUG_MODE:
                            logger.info(f'🤖 AI Classification result: {category}')
                        return category.upper() if category == 'n/a' else category
                if DEBUG_MODE:
                    logger.warning(f"🤖 AI Classification: Invalid result '{result}', defaulting to bình_thường")
                return 'bình_thường'
            else:
                if DEBUG_MODE:
                    logger.warning('🤖 AI Classification: No response from Google AI')
                return None
        except Exception as e:
            error_msg = str(e)
            if DEBUG_MODE:
                logger.error(f'❌ Lỗi AI Classification: {error_msg}')
            if key_manager and ('quota' in error_msg.lower() or '429' in error_msg):
                if DEBUG_MODE:
                    logger.info(f'🔄 AI Classification quota/rate limit detected, rotating API key...')
                try:
                    next_key = key_manager.rotate_to_next_key()
                    if DEBUG_MODE:
                        logger.info(f'🔑 AI Classification: Rotated to {key_manager.get_key_info()}')
                    genai.configure(api_key=next_key)
                    retry_model = genai.GenerativeModel(model_name=GOOGLE_AI_MODEL)
                    if DEBUG_MODE:
                        logger.info(f'🔄 AI Classification retry with new key...')
                    try:
                        response = await asyncio.wait_for(retry_model.generate_content_async(prompt), timeout=30.0)
                    except asyncio.TimeoutError:
                        if DEBUG_MODE:
                            logger.warning('⏰ Google AI Classification retry timeout (30s)')
                        return 'bình_thường'
                    if response and response.text:
                        result = response.text.strip().lower()
                        for category in ['cờ_bạc', 'mại_dâm', 'phản_động', 'bình_thường', 'n/a']:
                            if category in result:
                                if DEBUG_MODE:
                                    logger.info(f'✅ AI Classification retry successful: {category}')
                                return category.upper() if category == 'n/a' else category
                        if DEBUG_MODE:
                            logger.warning(f"🤖 AI Classification retry: Invalid result '{result}', defaulting to bình_thường")
                        return 'bình_thường'
                    else:
                        if DEBUG_MODE:
                            logger.warning('⚠️ AI Classification retry: No response from Google AI')
                        return None
                except Exception as retry_error:
                    if DEBUG_MODE:
                        logger.error(f'❌ AI Classification retry failed: {retry_error}')
                    return None
            return None

    async def classify_text(self, text: str, api_key: str=None, use_few_shot: bool=False, key_manager: GoogleAPIKeyManager=None) -> Dict[str, any]:
        if not text or not text.strip():
            return {'category': 'N/A', 'method': 'empty_text', 'confidence': 'high', 'matched_keywords': [], 'ai_result': None}
        regex_category, matched_keywords = self.classify_with_regex(text)
        if regex_category != 'bình_thường':
            return {'category': regex_category, 'method': 'regex', 'confidence': 'high', 'matched_keywords': matched_keywords, 'ai_result': None}
        if api_key and api_key != 'YOUR_GOOGLE_API_KEY' and (len(api_key) > 10):
            ai_result = await self.classify_with_ai(text, api_key, use_few_shot, key_manager)
            return {'category': ai_result if ai_result else 'bình_thường', 'method': 'ai' if ai_result else 'ai_failed', 'confidence': 'medium' if ai_result else 'low', 'matched_keywords': [], 'ai_result': ai_result}
        return {'category': regex_category, 'method': 'regex_only', 'confidence': 'medium', 'matched_keywords': matched_keywords, 'ai_result': None}
text_classifier = TextClassifier()

async def classify_conversation_content(text: str, api_key: str=None, use_few_shot: bool=False, key_manager: GoogleAPIKeyManager=None) -> str:
    try:
        result = await text_classifier.classify_text(text, api_key, use_few_shot, key_manager)
        if DEBUG_MODE:
            logger.info(f"📊 Classification result: {result['category']} (method: {result['method']}, confidence: {result['confidence']})")
            if result['matched_keywords']:
                logger.info(f"🔍 Matched keywords: {result['matched_keywords']}")
        return result['category']
    except Exception as e:
        if DEBUG_MODE:
            logger.error(f'❌ Error in classify_conversation_content: {e}')
        return 'N/A'

def get_classification_method(api_key: str=None) -> str:
    if api_key and api_key != 'YOUR_GOOGLE_API_KEY' and (api_key != '********') and (len(api_key) > 10):
        return 'ai'
    else:
        return 'regex_only'