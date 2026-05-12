import os
import logging
from typing import Optional
from fastapi import UploadFile
import PyPDF2
import docx
import io
import re
import unicodedata
logger = logging.getLogger(__name__)

class FileProcessor:

    def __init__(self):
        self.transcriber = None
        self.executor = None

    def set_executor(self, executor):
        self.executor = executor

    async def process_file(self, file: UploadFile) -> Optional[str]:
        filename = file.filename.lower()
        content = await file.read()
        try:
            if filename.endswith('.txt'):
                return content.decode('utf-8')
            elif filename.endswith('.pdf'):
                if self.executor:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(self.executor, self._extract_from_pdf, content)
                return self._extract_from_pdf(content)
            elif filename.endswith('.docx'):
                if self.executor:
                    import asyncio
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(self.executor, self._extract_from_docx, content)
                return self._extract_from_docx(content)
            elif filename.endswith(('.png', '.jpg', '.jpeg')):
                from .llm_client import gemini_client
                mime_type = 'image/png' if filename.endswith('.png') else 'image/jpeg'
                logger.info(f'🔍 Analyzing image {filename} (OCR + Description fallback)...')
                return await gemini_client.extract_text_from_image(content, mime_type)
            elif filename.endswith(('.wav', '.mp3', '.mp4')):
                logger.info(f'🎙️ Running STT on {filename}...')
                return await self._extract_from_audio(content, filename)
            else:
                logger.warning(f'Unsupported file type: {filename}')
                return None
        except Exception as e:
            logger.error(f'Error processing file {filename}: {e}')
            return None

    async def _extract_from_audio(self, content: bytes, filename: str) -> str:
        import uuid
        import os
        temp_path = f'temp_hub_{uuid.uuid4()}_{filename}'
        try:
            with open(temp_path, 'wb') as f:
                f.write(content)
            if not self.transcriber:
                return 'Error: Transcriber not initialized in FileProcessor'
            context = {'audio_path': temp_path, 'status': 'processing'}
            context = await self.transcriber.process(context)
            return context.get('transcript', '')
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def _extract_from_pdf(content: bytes) -> str:
        text = ''
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            if pdf_reader.is_encrypted:
                logger.error('⚠️ PDF file is encrypted/password protected')
                raise Exception('PDF file is encrypted and cannot be extracted')
            page_count = len(pdf_reader.pages)
            logger.info(f'📄 PDF has {page_count} pages, extracting text...')
            for i, page in enumerate(pdf_reader.pages):
                try:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + '\n'
                        logger.debug(f'  ✓ Page {i + 1}: {len(extracted)} chars')
                    else:
                        logger.warning(f'  ⚠ Page {i + 1}: No text extracted (possibly image-only)')
                except Exception as page_error:
                    logger.warning(f'  ❌ Page {i + 1} extraction failed: {page_error}')
                    continue
            if not text.strip():
                logger.error('⚠️ PDF extraction resulted in empty text (possibly scanned/image PDF)')
                raise Exception('PDF contains no extractable text. It may be a scanned image PDF requiring OCR.')
            logger.info(f'✅ PDF extraction complete: {len(text)} chars total')
        except Exception as e:
            logger.error(f'❌ PDF extraction error: {type(e).__name__}: {str(e)}')
            raise e
        return text

    @staticmethod
    def _extract_from_docx(content: bytes) -> str:
        text = ''
        try:
            doc = docx.Document(io.BytesIO(content))
            for para in doc.paragraphs:
                text += para.text + '\n'
        except Exception as e:
            logger.error(f'Docx extraction error: {e}')
            raise e
        return text

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ''
        text = unicodedata.normalize('NFC', text)

        def collapse_wide_caps(match):
            parts = re.split('\\s{2,}', match.group(0))
            cleaned_parts = [p.replace(' ', '') for p in parts]
            return ' '.join(cleaned_parts)
        wide_caps_pattern = '\\b(?:[A-ZÀ-Ỹ]{1,2}\\s){2,}[A-ZÀ-Ỹ]{1,2}\\b'
        text = re.sub(wide_caps_pattern, collapse_wide_caps, text)
        lines = text.split('\n')
        merged_lines = []
        if lines:
            current_line = lines[0].strip()
            for next_line in lines[1:]:
                next_line = next_line.strip()
                if not next_line:
                    if current_line:
                        merged_lines.append(current_line)
                    current_line = ''
                    continue
                if current_line and (not current_line.endswith(('.', '!', '?', ':'))):
                    if next_line and next_line[0].islower():
                        current_line += ' ' + next_line
                    else:
                        merged_lines.append(current_line)
                        current_line = next_line
                else:
                    if current_line:
                        merged_lines.append(current_line)
                    current_line = next_line
            if current_line:
                merged_lines.append(current_line)
        return '\n'.join(merged_lines)

    @staticmethod
    def chunk_text(text: str, chunk_size: int=1000, overlap: int=200) -> list[str]:
        if not text:
            return []
        text = FileProcessor.clean_text(text)
        chunks = []
        start = 0
        text_len = len(text)
        separators = ['\n\n', '\n', '. ', '? ', '! ', '; ', ', ', ' ']
        while start < text_len:
            end = start + chunk_size
            if end >= text_len:
                chunks.append(text[start:].strip())
                break
            split_point = -1
            found = False
            search_limit = max(start + chunk_size // 2, start)
            for sep in separators:
                idx = text.rfind(sep, search_limit, end)
                if idx != -1:
                    split_point = idx + len(sep)
                    found = True
                    break
            if not found:
                split_point = end
            chunk = text[start:split_point].strip()
            if chunk:
                chunks.append(chunk)
            if overlap > 0 and split_point < text_len:
                start = max(0, split_point - overlap)
            else:
                start = split_point
        return chunks
file_processor = FileProcessor()