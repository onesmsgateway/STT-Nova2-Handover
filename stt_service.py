from deepgram import DeepgramClient
from typing import Dict, Any, Optional
from config import DEEPGRAM_MODEL, DEEPGRAM_API_KEYS, DEBUG_MODE, REQUEST_TIMEOUT
from key_manager import BaseAPIKeyManager
import json
import httpx
import logging
logger = logging.getLogger(__name__)

class DeepgramAPIKeyManager(BaseAPIKeyManager):

    def rotate_to_next_key(self) -> str:
        return self.rotate_key()

def transcribe_prerecorded(api_key: str, path_to_file: str, extra_options: Optional[Dict[str, Any]]=None, key_manager: DeepgramAPIKeyManager=None):
    current_api_key = api_key
    if key_manager:
        current_api_key = key_manager.get_current_key()
        if DEBUG_MODE:
            logger.info(f'🔑 Deepgram: Sử dụng {key_manager.get_key_info()}')
    client = DeepgramClient(api_key=current_api_key)
    options: Dict[str, Any] = {'punctuate': True, 'model': DEEPGRAM_MODEL, 'language': 'vi', 'smart_format': True, 'diarize': True, 'utterances': True, 'detect_language': False, 'filler_words': True, 'numerals': True, 'profanity_filter': False, 'redact': False, 'paragraphs': True, 'diarize': True, 'keywords': ['xin chào', 'tổng đài', 'hỗ trợ', 'quý khách', 'xác nhận thông tin', 'số điện thoại', 'địa chỉ', 'đặt hàng', 'đơn hàng', 'liên hệ']}
    if extra_options:
        options.update(extra_options)
    try:
        import json
        import httpx
        if path_to_file.startswith(('http://', 'https://')):
            source = {'url': path_to_file}
            if DEBUG_MODE:
                logger.info(f'🔗 Gửi URL trực tiếp cho Deepgram: {path_to_file}')
            headers = {'Authorization': f'Token {current_api_key}', 'Content-Type': 'application/json'}
            api_url = 'https://api.deepgram.com/v1/listen'
            params = '&'.join([f'{k}={(str(v).lower() if isinstance(v, bool) else v)}' for k, v in options.items() if k != 'keywords'])
            if 'keywords' in options:
                for kw in options['keywords']:
                    params += f'&keywords={kw}'
            with httpx.Client(timeout=REQUEST_TIMEOUT) as http_client:
                resp = http_client.post(f'{api_url}?{params}', json=source, headers=headers)
                resp.raise_for_status()
                response = resp.json()
        else:
            if DEBUG_MODE:
                logger.info(f'📁 Gửi file local cho Deepgram: {path_to_file}')
            headers = {'Authorization': f'Token {current_api_key}', 'Content-Type': 'audio/*'}
            api_url = 'https://api.deepgram.com/v1/listen'
            params = '&'.join([f'{k}={(str(v).lower() if isinstance(v, bool) else v)}' for k, v in options.items() if k != 'keywords'])
            if 'keywords' in options:
                for kw in options['keywords']:
                    params += f'&keywords={kw}'
            with open(path_to_file, 'rb') as audio_file:
                with httpx.Client(timeout=REQUEST_TIMEOUT) as http_client:
                    resp = http_client.post(f'{api_url}?{params}', content=audio_file.read(), headers=headers)
                    resp.raise_for_status()
                    response = resp.json()
        if 'results' in response:
            if DEBUG_MODE:
                logger.info(f'✅ Deepgram API call successful (bypassed SDK validation)')
                logger.info(f'Response type: {type(response)}')
            return response
        else:
            if DEBUG_MODE:
                logger.info(f'⚠️ Using fallback format, returning raw response')
            return response
    except Exception as e:
        error_msg = str(e)
        if DEBUG_MODE:
            logger.info(f'❌ Lỗi khi gọi Deepgram API: {error_msg}')
        if key_manager and ('quota' in error_msg.lower() or '429' in error_msg or 'rate limit' in error_msg.lower()):
            if DEBUG_MODE:
                logger.info(f'🔄 Deepgram quota/rate limit detected, rotating API key...')
            try:
                next_key = key_manager.rotate_to_next_key()
                if DEBUG_MODE:
                    logger.info(f'🔑 Deepgram: Rotated to {key_manager.get_key_info()}')
                if path_to_file.startswith(('http://', 'https://')):
                    source = {'url': path_to_file}
                    if DEBUG_MODE:
                        logger.info(f'🔄 Deepgram retry with new key: {path_to_file}')
                    headers = {'Authorization': f'Token {next_key}', 'Content-Type': 'application/json'}
                    api_url = 'https://api.deepgram.com/v1/listen'
                    params = '&'.join([f'{k}={(str(v).lower() if isinstance(v, bool) else v)}' for k, v in options.items() if k != 'keywords'])
                    if 'keywords' in options:
                        for kw in options['keywords']:
                            params += f'&keywords={kw}'
                    with httpx.Client(timeout=REQUEST_TIMEOUT) as http_client:
                        resp = http_client.post(f'{api_url}?{params}', json=source, headers=headers)
                        resp.raise_for_status()
                        response = resp.json()
                else:
                    if DEBUG_MODE:
                        logger.info(f'🔄 Deepgram retry with new key: {path_to_file}')
                    headers = {'Authorization': f'Token {next_key}', 'Content-Type': 'audio/*'}
                    api_url = 'https://api.deepgram.com/v1/listen'
                    params = '&'.join([f'{k}={(str(v).lower() if isinstance(v, bool) else v)}' for k, v in options.items() if k != 'keywords'])
                    if 'keywords' in options:
                        for kw in options['keywords']:
                            params += f'&keywords={kw}'
                    with open(path_to_file, 'rb') as audio_file:
                        with httpx.Client(timeout=REQUEST_TIMEOUT) as http_client:
                            resp = http_client.post(f'{api_url}?{params}', content=audio_file.read(), headers=headers)
                            resp.raise_for_status()
                            response = resp.json()
                if 'results' in response:
                    if DEBUG_MODE:
                        logger.info(f'✅ Deepgram retry successful with {key_manager.get_key_info()}')
                        logger.info(f'Retry response type: {type(response)}')
                    return response
                else:
                    return response
            except Exception as retry_error:
                if DEBUG_MODE:
                    logger.info(f'❌ Deepgram retry failed with new key: {retry_error}')
                raise e
        raise e