import os
import logging
import asyncio
from typing import Optional, List, Dict, Any
from .rate_limiter import GeminiRateLimiter
logger = logging.getLogger(__name__)

def get_groq_api_keys() -> List[str]:
    raw_keys_str = os.getenv('GROQ_API_KEYS', '')
    raw_single_key = os.getenv('GROQ_API_KEY', '')
    logger.info(f"🔍 [DEBUG] Raw GROQ_API_KEYS env: '{(raw_keys_str[:20] if raw_keys_str else '')}...' (len={len(raw_keys_str)})")
    logger.info(f"🔍 [DEBUG] Raw GROQ_API_KEY env: '{(raw_single_key[:20] if raw_single_key else '')}...' (len={len(raw_single_key)})")
    keys = []
    if raw_keys_str:
        keys = [k.strip().strip("'").strip('"') for k in raw_keys_str.split(',') if k.strip()]
    if not keys and raw_single_key:
        parsed = [k.strip().strip("'").strip('"') for k in raw_single_key.split(',') if k.strip()]
        keys.extend(parsed)
    for i, k in enumerate(keys):
        logger.info(f"🔍 [DEBUG] Parsed key {i + 1}: '{k[:12]}...{k[-4:]}' (len={len(k)})")
    return keys
GROQ_API_KEYS = get_groq_api_keys()
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

class GroqClient:

    def __init__(self, api_keys: List[str]=None, model: str=None):
        self.api_keys = api_keys or GROQ_API_KEYS
        self.model = model or GROQ_MODEL
        self.current_key_index = 0
        self._clients: Dict[str, Any] = {}
        if not self.api_keys:
            logger.warning('⚠️ GROQ_API_KEYS not set. Groq fallback will not be available.')
        else:
            self.rate_limiter = GeminiRateLimiter(self.api_keys, rpm_per_key=30)
            logger.info(f'✅ GroqClient initialized with {len(self.api_keys)} API key(s) and Rate Limiter (30 RPM)')

    async def _get_next_key_async(self) -> str:
        if not self.api_keys:
            raise ValueError('No Groq API keys available')
        await self.rate_limiter.wait_for_capacity()
        key = self.rate_limiter.get_next_available_key()
        if not key:
            raise ValueError('All Groq API keys exhausted or in cooldown')
        return key

    def _get_next_key(self) -> str:
        if not self.api_keys:
            raise ValueError('No Groq API keys available')
        key = self.api_keys[self.current_key_index]
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        return key

    def _get_client(self, api_key: str):
        if api_key not in self._clients:
            try:
                from groq import Groq
                self._clients[api_key] = Groq(api_key=api_key)
            except ImportError:
                logger.error('❌ Groq SDK not installed. Run: pip install groq')
                return None
            except Exception as e:
                logger.error(f'❌ Failed to initialize Groq client: {e}')
                return None
        return self._clients[api_key]

    @property
    def is_available(self) -> bool:
        return bool(self.api_keys)

    async def chat(self, prompt: str, history: Optional[List[Dict]]=None) -> str:
        if not self.is_available:
            raise RuntimeError('Groq client not available. Set GROQ_API_KEY environment variable.')
        try:
            messages = []
            if history:
                for msg in history:
                    role = msg.get('role', 'user')
                    if role == 'model':
                        role = 'assistant'
                    messages.append({'role': role, 'content': msg.get('content', '')})
            messages.append({'role': 'user', 'content': prompt})
            import asyncio
            response = await asyncio.to_thread(self._call_groq_sync, messages)
            return response
        except Exception as e:
            logger.error(f'❌ Groq API error: {e}')
            raise

    def _call_groq_sync(self, messages: List[Dict]) -> str:
        max_retries = len(self.api_keys) * 2
        last_error = None
        for attempt in range(max_retries):
            current_key = self._get_next_key()
            client = self._get_client(current_key)
            if not client:
                continue
            try:
                logger.info(f'🔄 Groq request using key {current_key[:8]}... (attempt {attempt + 1})')
                response = client.chat.completions.create(model=self.model, messages=messages, temperature=0.7, max_tokens=2048, top_p=0.95)
                if response.choices and response.choices[0].message:
                    return response.choices[0].message.content
            except Exception as e:
                last_error = e
                logger.warning(f'⚠️ Groq key {current_key[:8]}... failed: {e}')
                continue
        raise RuntimeError(f'All Groq API keys exhausted. Last error: {last_error}')

    async def summarize_text(self, text: str) -> str:
        prompt = f'\n        Tóm tắt văn bản sau bằng tiếng Việt, ngắn gọn và súc tích (tối đa 150 từ):\n        \n        {text[:8000]}\n        \n        Chỉ trả về nội dung tóm tắt, không thêm lời dẫn.\n        '
        return await self.chat(prompt)

    async def classify_text(self, text: str) -> Dict[str, Any]:
        import json
        prompt = f'\n        Phân loại văn bản sau vào một trong các danh mục:\n        - Giáo dục\n        - Văn hóa\n        - Khoa học\n        - Công nghệ\n        - Xã hội\n        - Kinh tế\n        - Thể thao\n        - Giải trí\n        - Khác\n        \n        Văn bản: "{text[:2000]}"\n        \n        Trả về JSON: {{"category": "...", "confidence": 0.0-1.0, "keywords": ["..."]}}\n        '
        try:
            response = await self.chat(prompt)
            cleaned = response.replace('```json', '').replace('```', '').strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f'Classification error: {e}')
            return {'category': 'Khác', 'confidence': 0.0, 'keywords': []}

    def get_availability_status(self) -> Dict[str, Any]:
        if not self.api_keys:
            return {'available_keys': 0, 'total_keys': 0, 'status': 'unavailable', 'avg_cooldown_remaining': 0}
        if hasattr(self, 'rate_limiter') and self.rate_limiter:
            return self.rate_limiter.get_availability_status()
        return {'available_keys': len(self.api_keys), 'total_keys': len(self.api_keys), 'status': 'ok', 'avg_cooldown_remaining': 0}
groq_client = GroqClient()