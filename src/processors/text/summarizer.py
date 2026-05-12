from typing import Dict, Any
from src.core.logger import setup_logger
from src.interfaces.base import BaseProcessor
from src.core.config import MAX_WORDS, GOOGLE_API_KEY, GOOGLE_API_KEYS
import sys
import os
sys.path.append(os.getcwd())
from summarizer import summarize_with_google_ai, summarize_transcript, GoogleAPIKeyManager
logger = setup_logger(__name__)

class SummarizerProcessor(BaseProcessor):

    def __init__(self):
        self.google_key_manager = GoogleAPIKeyManager(GOOGLE_API_KEYS) if GOOGLE_API_KEYS else None
        self.default_api_key = GOOGLE_API_KEY

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        transcript = context.get('transcript')
        if not transcript:
            return context
        max_words = context.get('options', {}).get('max_words', MAX_WORDS)
        try:
            summary = await summarize_with_google_ai(self.default_api_key, transcript.strip(), max_words=max_words, key_manager=self.google_key_manager)
            if not summary:
                logger.info('Fallback to algorithmic summary')
                summary = summarize_transcript(transcript.strip(), max_words=max_words)
                method = 'algorithm'
            else:
                method = 'google_ai'
            context['summary'] = summary
            context['summary_method'] = method
            logger.info(f'✅ Summary created using {method}')
        except Exception as e:
            logger.error(f'Summary error: {e}')
            context['summary_error'] = str(e)
        return context