import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import logging
import random
import time
from typing import List, Optional, Dict, Any
import config
from .rate_limiter import GeminiRateLimiter, init_rate_limiter
from .groq_client import groq_client
from .local_embeddings import local_embedding_client
logger = logging.getLogger(__name__)

class GeminiClient:

    def __init__(self, api_keys: List[str]=None, model_name: str=None, rpm_per_key: int=15):
        self.api_keys = api_keys or config.GOOGLE_API_KEYS
        if not self.api_keys:
            logger.warning('⚠️ No Google API Keys provided for GeminiClient!')
        self.current_key_index = 0
        self.model_name = model_name or config.GOOGLE_AI_MODEL
        self.rate_limiter = init_rate_limiter(self.api_keys, rpm_per_key)
        self.safety_settings = {HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE, HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE}
        self.generation_config = {'temperature': 0.7, 'top_p': 0.95, 'top_k': 64, 'max_output_tokens': 2048}

    async def _get_next_key_async(self) -> str:
        if not self.api_keys:
            raise ValueError('No Google API keys available')
        await self.rate_limiter.wait_for_capacity()
        key = self.rate_limiter.get_next_available_key()
        if not key:
            raise ValueError('All API keys exhausted or in cooldown')
        return key

    def _get_next_key(self) -> str:
        if not self.api_keys:
            raise ValueError('No Google API keys available')
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    async def extract_text_from_image(self, image_bytes: bytes, mime_type: str='image/jpeg') -> str:
        max_retries = len(self.api_keys) * 2
        attempts = 0
        prompt = "\n        Phân tích hình ảnh này và thực hiện theo thứ tự ưu tiên:\n        1. Nếu có văn bản (chữ viết), hãy trích xuất toàn bộ văn bản một cách chính xác.\n        2. Nếu hình ảnh không có văn bản hoặc văn bản không thể hiện hết nội dung, hãy mô tả chi tiết nội dung bức ảnh (đối tượng, bối cảnh, hành động, màu sắc).\n        Chỉ trả về nội dung trích xuất hoặc mô tả, không thêm lời dẫn kiểu 'Đây là...' hay lời bình luận của AI.\n        "
        while attempts < max_retries:
            current_key = self._get_next_key()
            try:
                genai.configure(api_key=current_key)
                model = genai.GenerativeModel(model_name=self.model_name, safety_settings=self.safety_settings)
                image_data = {'mime_type': mime_type, 'data': image_bytes}
                response = await model.generate_content_async([prompt, image_data])
                if response.text:
                    return response.text.strip()
                else:
                    return ''
            except Exception as e:
                error_str = str(e)
                logger.error(f'Gemini Vision Error with key {current_key[:8]}...: {error_str}')
                attempts += 1
                time.sleep(1)
        return ''

    async def chat(self, prompt: str, system_instruction: str=None, history: List[Dict[str, str]]=None) -> str:
        import asyncio
        import re
        max_retries = len(self.api_keys) * 2
        attempts = 0
        while attempts < max_retries:
            current_key = await self._get_next_key_async()
            try:
                self.rate_limiter.record_request(current_key)
                genai.configure(api_key=current_key)
                model = genai.GenerativeModel(model_name=self.model_name, safety_settings=self.safety_settings, generation_config=self.generation_config, system_instruction=system_instruction)
                if history:
                    gemini_history = []
                    for msg in history:
                        role = 'user'
                        if msg.get('role') == 'assistant' or msg.get('role') == 'model':
                            role = 'model'
                        gemini_history.append({'role': role, 'parts': [msg.get('content', '')]})
                    chat_session = model.start_chat(history=gemini_history)
                    response = await chat_session.send_message_async(prompt)
                else:
                    response = await model.generate_content_async(prompt)
                if response.text:
                    return response.text
                else:
                    logger.warning(f'Key {current_key[:8]}... returned empty response')
                    attempts += 1
            except Exception as e:
                error_str = str(e)
                logger.error(f'Gemini Error with key {current_key[:8]}...: {error_str}')
                if '429' in error_str or 'quota' in error_str.lower():
                    if groq_client.is_available:
                        logger.warning('🚫 Gemini Quota Exceeded. Switching to Groq immediately (Fast Fallback).')
                        break
                    retry_match = re.search('retry in (\\d+\\.?\\d*)', error_str.lower())
                    if retry_match:
                        retry_delay = min(float(retry_match.group(1)), 30)
                        self.rate_limiter.set_key_cooldown(current_key, retry_delay)
                        logger.warning(f'⏳ Rate limited. Key {current_key[:8]}... in cooldown {retry_delay}s')
                        await asyncio.sleep(1)
                    else:
                        backoff_time = min(5 * (attempts + 1), 30)
                        self.rate_limiter.set_key_cooldown(current_key, backoff_time)
                        logger.warning(f'⏳ Rate limited. Key {current_key[:8]}... in cooldown {backoff_time}s')
                        await asyncio.sleep(backoff_time)
                else:
                    await asyncio.sleep(1)
                attempts += 1
        if groq_client.is_available:
            logger.warning('🔄 All Gemini keys exhausted. Falling back to Groq...')
            try:
                return await groq_client.chat(prompt, history)
            except Exception as groq_error:
                logger.error(f'❌ Groq fallback also failed: {groq_error}')
                raise RuntimeError(f'All LLM providers failed. Gemini exhausted, Groq error: {groq_error}')
        else:
            raise RuntimeError('All Gemini API keys exhausted and Groq fallback not configured.')

    async def chat_with_tools(self, prompt: str, tools: List[Dict[str, Any]]=None, history: List[Dict[str, Any]]=None, system_instruction: str=None) -> Dict[str, Any]:
        import asyncio
        from google.generativeai.types import FunctionDeclaration, Tool
        max_retries = len(self.api_keys) * 2
        attempts = 0
        while attempts < max_retries:
            current_key = await self._get_next_key_async()
            try:
                self.rate_limiter.record_request(current_key)
                genai.configure(api_key=current_key)
                gemini_tools = None
                if tools:
                    function_declarations = []
                    for tool in tools:
                        func_decl = FunctionDeclaration(name=tool.get('name'), description=tool.get('description', ''), parameters=tool.get('parameters', {}))
                        function_declarations.append(func_decl)
                    gemini_tools = [Tool(function_declarations=function_declarations)]
                model = genai.GenerativeModel(model_name=self.model_name, safety_settings=self.safety_settings, generation_config=self.generation_config, system_instruction=system_instruction, tools=gemini_tools)
                gemini_history = []
                if history:
                    for msg in history:
                        role = msg.get('role', 'user')
                        if role == 'assistant':
                            role = 'model'
                        parts = []
                        if msg.get('function_call'):
                            from google.generativeai.types import FunctionCall
                            fc = msg['function_call']
                            parts.append(FunctionCall(name=fc['name'], args=fc.get('args', {})))
                        elif msg.get('function_response'):
                            from google.generativeai.types import FunctionResponse
                            fr = msg['function_response']
                            parts.append(FunctionResponse(name=fr['name'], response=fr.get('response', {})))
                        elif msg.get('content'):
                            parts.append(msg['content'])
                        if parts:
                            gemini_history.append({'role': role, 'parts': parts})
                chat_session = model.start_chat(history=gemini_history)
                response = await chat_session.send_message_async(prompt)
                if response.candidates and response.candidates[0].content.parts:
                    part = response.candidates[0].content.parts[0]
                    if hasattr(part, 'function_call') and part.function_call.name:
                        return {'type': 'function_call', 'content': None, 'function_call': {'name': part.function_call.name, 'args': dict(part.function_call.args) if part.function_call.args else {}}}
                return {'type': 'text', 'content': response.text if response.text else '', 'function_call': None}
            except Exception as e:
                error_str = str(e)
                logger.error(f'Gemini Function Calling Error with key {current_key[:8]}...: {error_str}')
                if '429' in error_str or 'quota' in error_str.lower():
                    self.rate_limiter.set_key_cooldown(current_key, 30)
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(1)
                attempts += 1
        raise RuntimeError('All Gemini API keys exhausted for function calling.')

    async def get_embedding(self, text: str) -> List[float]:
        import asyncio
        import re
        text = text.replace('\n', ' ')
        max_retries = len(self.api_keys) * 2
        attempts = 0

        def _sync_embed_content(api_key: str, content: str):
            genai.configure(api_key=api_key)
            result = genai.embed_content(model='models/text-embedding-004', content=content, task_type='retrieval_document', title='Embedding')
            return result['embedding']
        while attempts < max_retries:
            current_key = await self._get_next_key_async()
            try:
                self.rate_limiter.record_request(current_key)
                result = await asyncio.wait_for(asyncio.to_thread(_sync_embed_content, current_key, text), timeout=30.0)
                return result
            except asyncio.TimeoutError:
                logger.error(f'Embedding timeout (30s) with key {current_key[:8]}...')
                attempts += 1
            except Exception as e:
                error_str = str(e)
                logger.error(f'Embedding Error with key {current_key[:8]}...: {error_str}')
                if '429' in error_str or 'quota' in error_str.lower():
                    if local_embedding_client.is_available:
                        logger.warning('🚫 Gemini Quota Exceeded. Switching to Local Embedding immediately (Fast Fallback).')
                        break
                    retry_match = re.search('retry in (\\d+\\.?\\d*)', error_str.lower())
                    if retry_match:
                        retry_delay = min(float(retry_match.group(1)), 30)
                        self.rate_limiter.set_key_cooldown(current_key, retry_delay)
                        logger.warning(f'⏳ Embedding rate limited. Key {current_key[:8]}... in cooldown {retry_delay}s')
                        await asyncio.sleep(1)
                    else:
                        backoff_time = min(5 * (attempts + 1), 30)
                        self.rate_limiter.set_key_cooldown(current_key, backoff_time)
                        logger.warning(f'⏳ Embedding rate limited. Key {current_key[:8]}... in cooldown {backoff_time}s')
                        await asyncio.sleep(1)
                else:
                    await asyncio.sleep(1)
                attempts += 1
        if local_embedding_client.is_available:
            logger.warning('🔄 All Gemini embedding keys exhausted. Falling back to local embeddings...')
            try:
                return local_embedding_client.get_embedding(text)
            except Exception as local_error:
                logger.error(f'❌ Local embedding fallback also failed: {local_error}')
                raise RuntimeError(f'All embedding providers failed. Gemini exhausted, Local error: {local_error}')
        else:
            raise RuntimeError('Failed to get embedding from Gemini and local fallback not available')

    async def summarize_text(self, text: str) -> str:
        prompt = f'\n        Hãy tóm tắt văn bản sau đây một cách súc tích, nắm bắt các ý chính quan trọng nhất. \n        Độ dài khoảng 150-200 từ.\n        \n        Văn bản:\n        {text[:20000]}  # Limit context window just in case\n        '
        return await self.chat(prompt)

    async def classify_text(self, text: str) -> str:
        prompt = f'\n        Hãy phân loại văn bản sau vào 1 trong các nhóm: \n        [Giáo dục, Y tế, Kinh doanh, Pháp luật, Công nghệ, Giải trí, Đời sống, Khác].\n        Chỉ trả về tên nhóm, không giải thích gì thêm.\n        \n        Văn bản:\n        {text[:5000]}\n        '
        return await self.chat(prompt)

    async def check_content_safety(self, text: str) -> Dict[str, Any]:
        prompt = f'\n        Phân tích văn bản sau và xác định xem nó có thuộc một trong các nhóm vi phạm sau không:\n        1. Cờ bạc (Gambling): Cá độ, lô đề, cờ bạc online/offline.\n        2. Mại dâm (Prostitution/Adult): Mua bán dâm, massage kích dục, nội dung khiêu dâm người lớn.\n        3. Tục tĩu/Xúc phạm (Profanity/Hate Speech): Chửi thề, ngôn ngữ thô tục, xúc phạm nghiêm trọng.\n\n        Văn bản: "{text[:1000]}"\n\n        Trả về kết quả dưới dạng JSON duy nhất:\n        {{\n            "is_safe": true/false,  \n            "category": "Safe" | "Gambling" | "Prostitution" | "Profanity",\n            "reason": "Giải thích ngắn gọn"\n        }}\n        '
        try:
            response_text = await self.chat(prompt)
            cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
            return json.loads(cleaned_text)
        except Exception as e:
            logger.error(f'Safety check error: {e}')
            return {'is_safe': True, 'category': 'Error', 'reason': str(e)}
import json
gemini_client = GeminiClient()