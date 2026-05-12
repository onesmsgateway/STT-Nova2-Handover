from typing import Dict, Any, Optional
import os
from src.core.logger import setup_logger
from src.interfaces.base import BaseProcessor
logger = setup_logger(__name__)

class DocumentProcessor(BaseProcessor):

    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        file_path = context.get('document_path') or context.get('audio_path')
        if not file_path:
            return context
        if file_path.lower().endswith('.pdf'):
            text = self._extract_pdf(file_path)
        elif file_path.lower().endswith('.docx'):
            text = self._extract_docx(file_path)
        else:
            return context
        if text:
            context['transcript'] = text
            context['doc_content'] = text
            logger.info(f'✅ Extracted text from document: {len(text)} chars')
        else:
            context['error'] = 'Empty or unreadable document'
        return context

    def _extract_pdf(self, path: str) -> Optional[str]:
        try:
            import PyPDF2
            text = ''
            with open(path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() + '\n'
            return text
        except Exception as e:
            logger.error(f'Error reading PDF {path}: {e}')
            return None

    def _extract_docx(self, path: str) -> Optional[str]:
        try:
            import docx
            doc = docx.Document(path)
            text = '\n'.join([para.text for para in doc.paragraphs])
            return text
        except Exception as e:
            logger.error(f'Error reading DOCX {path}: {e}')
            return None