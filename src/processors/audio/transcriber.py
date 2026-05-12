import asyncio
from typing import Dict, Any, Optional
from src.core.logger import setup_logger
from src.core.config import DEEPGRAM_API_KEY, DEEPGRAM_API_KEYS
from src.interfaces.base import BaseProcessor
from src.processors.audio.smart_model import SmartModelManager
import sys
import os
sys.path.append(os.getcwd())
from stt_service import transcribe_prerecorded, DeepgramAPIKeyManager
from phowhisper_engine import transcribe as phowhisper_transcribe
logger = setup_logger(__name__)

class Transcriber(BaseProcessor):

    def __init__(self):
        self.deepgram_key_manager = DeepgramAPIKeyManager(DEEPGRAM_API_KEYS) if DEEPGRAM_API_KEYS else None

        def load_phowhisper_model():
            import torch
            from transformers import pipeline
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.info(f'Loading PhoWhisper on {device}')
            return 'PhoWhisper_Model_Loaded'
        self.phowhisper_manager = SmartModelManager(load_phowhisper_model, idle_timeout=1800)

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        audio_path = context.get('audio_path')
        if not audio_path:
            context['transcription_error'] = 'No audio path provided'
            return context
        success = await self._transcribe_deepgram(audio_path, context)
        if success:
            confidence = context.get('transcription_confidence', 1.0)
            if confidence >= 0.5:
                logger.info(f'✅ Deepgram result accepted with confidence: {confidence}')
                return context
            else:
                logger.info(f'⚠️ Low confidence ({confidence}) from Deepgram, trying PhoWhisper fallback...')
        else:
            logger.warning('Deepgram transcription failed, falling back to PhoWhisper')
        await self._transcribe_phowhisper(audio_path, context)
        return context

    async def _transcribe_deepgram(self, audio_path: str, context: Dict) -> bool:
        try:
            logger.info(f'Transcribing with Deepgram: {audio_path}')
            response = transcribe_prerecorded(api_key=DEEPGRAM_API_KEY, audio_path=audio_path, options={}, key_manager=self.deepgram_key_manager)
            transcript = ''
            confidence = 0.0
            if response and 'results' in response:
                channels = response['results'].get('channels', [])
                if channels and channels[0]['alternatives']:
                    alternative = channels[0]['alternatives'][0]
                    transcript = alternative.get('transcript', '')
                    confidence = alternative.get('confidence', 0.0)
            if transcript:
                context['transcript'] = transcript
                context['transcription_confidence'] = confidence
                context['engine_used'] = 'deepgram'
                logger.info(f'✅ Deepgram transcription success (confidence: {confidence})')
                return True
            return False
        except Exception as e:
            logger.error(f'Deepgram error: {e}')
            return False

    async def _transcribe_phowhisper(self, audio_path: str, context: Dict) -> bool:
        try:
            logger.info('Requesting PhoWhisper model...')
            model = await self.phowhisper_manager.get_model()
            logger.info(f'Transcribing with PhoWhisper: {audio_path}')
            result = await asyncio.to_thread(phowhisper_transcribe, audio_path)
            context['transcript'] = result.get('text', '') or result.get('transcript', '')
            context['engine_used'] = 'phowhisper'
            logger.info('✅ PhoWhisper transcription success')
            return True
        except Exception as e:
            logger.error(f'PhoWhisper error: {e}')
            context['transcription_error'] = str(e)
            return False