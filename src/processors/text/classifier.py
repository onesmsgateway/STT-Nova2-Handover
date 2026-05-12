from typing import Dict, Any
from src.core.logger import setup_logger
from src.interfaces.base import BaseProcessor
from src.core.config import GOOGLE_CLASSIFICATION_API_KEYS, GOOGLE_API_KEY
import sys
import os
sys.path.append(os.getcwd())
from text_classifier import classify_conversation_content, GoogleAPIKeyManager as ClassifierKeyManager
logger = setup_logger(__name__)

class ClassifierProcessor(BaseProcessor):

    def __init__(self):
        self.key_manager = ClassifierKeyManager(GOOGLE_CLASSIFICATION_API_KEYS) if GOOGLE_CLASSIFICATION_API_KEYS else None
        self.default_api_key = GOOGLE_API_KEY

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        transcript = context.get('transcript')
        if not transcript:
            return context
        try:
            call_topic = await classify_conversation_content(text=transcript.strip(), api_key=self.default_api_key, use_few_shot=False, key_manager=self.key_manager)
            context['call_topic'] = call_topic
            logger.info(f'✅ Classified topic: {call_topic}')
        except Exception as e:
            logger.error(f'Classification error: {e}')
            context['call_topic'] = 'N/A'
            context['classification_error'] = str(e)
        return context