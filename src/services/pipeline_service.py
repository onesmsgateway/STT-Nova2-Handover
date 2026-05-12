import asyncio
from typing import Dict, Any, List
from src.core.logger import setup_logger
from src.processors.common.downloader import Downloader
from src.processors.audio.enhancer import AudioEnhancer
from src.processors.audio.transcriber import Transcriber
from src.services.notification_service import NotificationService
from src.processors.text.summarizer import SummarizerProcessor
from src.processors.text.classifier import ClassifierProcessor
from src.processors.text.document_parser import DocumentProcessor
from src.services.tts_service import TTSService
logger = setup_logger(__name__)

class PipelineService:

    def __init__(self):
        self.downloader = Downloader(save_dir='resource')
        self.enhancer = AudioEnhancer()
        self.transcriber = Transcriber()
        self.summarizer = SummarizerProcessor()
        self.classifier = ClassifierProcessor()
        self.doc_connector = DocumentProcessor()
        self.notifier = NotificationService()
        self.tts_service = TTSService()

    async def initialize(self):
        await self.notifier.start()

    async def tts_speak(self, text: str, language: str='vi', **kwargs) -> str:
        import uuid
        import os
        output_filename = f'tts_{uuid.uuid4()}.wav'
        output_path = f'static/{output_filename}'
        os.makedirs('static', exist_ok=True)
        success = await self.tts_service.speak(text, output_path, language=language, **kwargs)
        return output_path if success else None

    async def voice_clone(self, text: str, reference_path: str, rate: str='+0%') -> str:
        import uuid
        import os
        output_filename = f'clone_{uuid.uuid4()}.wav'
        output_path = f'static/{output_filename}'
        os.makedirs('static', exist_ok=True)
        try:
            logger.info('🎙️ Transcribing reference audio for cloning context...')
            ref_context = {'audio_path': reference_path, 'status': 'processing'}
            ref_context = await self.transcriber.process(ref_context)
            ref_text = ref_context.get('transcript', '')
            logger.info(f'📝 Reference Text: {ref_text[:50]}...')
        except Exception as e:
            logger.warning(f'⚠️ Failed to transcribe reference audio: {e}. Cloning might proceed without ref_text if model allows.')
            ref_text = ''
        success = await self.tts_service.clone_voice(reference_path, text, output_path, ref_text=ref_text, options={'rate': rate})
        return output_path if success else None

    async def process_request(self, urls: List[str], options: Dict[str, Any]=None) -> List[Dict[str, Any]]:
        results = []
        for url in urls:
            try:
                context = {'original_url': url, 'options': options or {}, 'status': 'processing'}
                logger.info(f'🚀 Pipeline Start: {url}')
                file_path = self.downloader.download_file(url)
                context['audio_path'] = file_path
                context['document_path'] = file_path
                is_document = file_path.lower().endswith(('.pdf', '.docx'))
                if is_document:
                    context = await self.doc_connector.process(context)
                else:
                    context = await self.enhancer.process(context)
                    context = await self.transcriber.process(context)
                if context.get('transcript'):
                    context = await self.summarizer.process(context)
                    context = await self.classifier.process(context)
                context['status'] = 'completed' if context.get('transcript') else 'failed'
                results.append(context)
                if 'audio_path' in context and context['audio_path'] != url:
                    pass
            except Exception as e:
                logger.error(f'❌ Pipeline Error: {e}')
                results.append({'original_url': url, 'status': 'error', 'error': str(e)})
        return results