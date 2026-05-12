from typing import Dict, Any, Optional
import logging
from src.core.logger import setup_logger
from src.core.config import AUDIO_PROCESSING_MODE, DEBUG_MODE
from src.interfaces.base import BaseProcessor
logger = setup_logger(__name__)

class AudioEnhancer(BaseProcessor):

    def __init__(self, processing_mode: str=AUDIO_PROCESSING_MODE):
        self.processing_mode = processing_mode

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        audio_path = context.get('audio_path')
        if not audio_path:
            logger.warning('No audio_path in context for AudioEnhancer')
            return context
        if self.processing_mode == 'off':
            logger.info('AudioEnhancer OFF: Skipping enhancement')
            return context
        try:
            import sys
            import os
            sys.path.append(os.getcwd())
            from audio_enhanced import process_audio_comprehensive
            logger.info(f'Running enhancement mode: {self.processing_mode}')
            result = process_audio_comprehensive(audio_path, processing_mode=self.processing_mode)
            if result['success'] and 'output_path' in result:
                enhanced_path = result['output_path']
                context['original_audio_path'] = audio_path
                context['audio_path'] = enhanced_path
                context['enhancement_info'] = result
                logger.info(f'✅ Enhanced audio saved to: {enhanced_path}')
            else:
                logger.warning(f"⚠️ Enhancement failed or returned no output: {result.get('message')}")
                context['enhancement_error'] = result.get('message')
        except Exception as e:
            logger.error(f'❌ Error in AudioEnhancer: {e}')
            context['enhancement_error'] = str(e)
        return context