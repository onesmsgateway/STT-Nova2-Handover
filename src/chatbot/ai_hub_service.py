import os
import uuid
import logging
import asyncio
import httpx
from typing import Optional, Dict, Any, List
import config
from .file_processor import file_processor
logger = logging.getLogger(__name__)

class AIHubService:

    def __init__(self, storage_dir: str='resource/ai_hub'):
        from src.core.task_store import task_store
        self.storage_dir = storage_dir
        self.task_store = task_store
        self.executor = None
        os.makedirs(self.storage_dir, exist_ok=True)

    def set_executor(self, executor):
        self.executor = executor

    async def enqueue_task(self, file_bytes: bytes, filename: str, webhook_url: Optional[str]=None, metadata: Optional[Dict]=None, enable_summary: bool=False, enable_classification: bool=False):
        task_id = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1]
        file_path = os.path.join(self.storage_dir, f'{task_id}{ext}')
        with open(file_path, 'wb') as f:
            f.write(file_bytes)
        self.task_store.create_task(task_id, {'filename': filename, 'webhook_url': webhook_url, 'metadata': metadata, 'options': {'summary': enable_summary, 'classification': enable_classification}})
        asyncio.create_task(self._process_task_background(task_id, file_path, filename, webhook_url, metadata, enable_summary, enable_classification))
        return task_id

    async def _process_task_background(self, task_id: str, file_path: str, original_name: str, webhook_url: Optional[str], metadata: Optional[Dict], enable_summary: bool, enable_classification: bool):
        logger.info(f'🚀 [AI Hub] Starting Stateless Task {task_id} for {original_name}')
        self.task_store.update_task(task_id, status='processing', progress=5)
        try:
            from fastapi import UploadFile
            import io
            from .llm_client import gemini_client
            with open(file_path, 'rb') as f:
                content = f.read()
            base_file = UploadFile(filename=original_name, file=io.BytesIO(content))
            text = await file_processor.process_file(base_file)
            if not text:
                raise Exception('Không thể trích xuất nội dung từ file')
            if self.executor:
                loop = asyncio.get_running_loop()
                chunks = await loop.run_in_executor(self.executor, file_processor.chunk_text, text)
            else:
                chunks = file_processor.chunk_text(text)
            logger.info(f'📦 [AI Hub] File split into {len(chunks)} chunks')
            self.task_store.update_task(task_id, progress=20)
            processed_data = []
            key_count = len(gemini_client.api_keys)
            concurrency_limit = max(1, key_count)
            semaphore = asyncio.Semaphore(concurrency_limit)
            logger.info(f'⚡ [AI Hub] Parallelizing vectorization with {concurrency_limit} concurrent requests')

            async def get_embedding_safe(chunk_text, index):
                async with semaphore:
                    try:
                        logger.info(f'🔄 [AI Hub] Embedding chunk {index + 1}/{len(chunks)}...')
                        emb = await gemini_client.get_embedding(chunk_text)
                        logger.info(f'✅ [AI Hub] Chunk {index + 1}/{len(chunks)} embedded successfully')
                        return {'content': chunk_text, 'vector': emb}
                    except Exception as e:
                        error_msg = str(e)
                        is_quota_error = 'quota' in error_msg.lower() or 'rate limit' in error_msg.lower() or '429' in error_msg
                        debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
                        if debug_mode and is_quota_error:
                            logger.warning(f'⚠️ [AI Hub DEBUG] Quota exhausted for chunk {index + 1}, using FAKE embedding (768-dim zeros)')
                            fake_embedding = [0.0] * 768
                            return {'content': chunk_text, 'vector': fake_embedding}
                        else:
                            logger.error(f'❌ [AI Hub] Failed to embed chunk {index + 1}/{len(chunks)}: {e}')
                            return None
            tasks = [get_embedding_safe(chunk, i) for i, chunk in enumerate(chunks)]
            results = await asyncio.gather(*tasks)
            debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
            failed_chunk_indices = []
            if debug_mode:
                processed_data = []
                for i, (result, chunk_text) in enumerate(zip(results, chunks)):
                    if result is None:
                        logger.warning(f'⚠️ [AI Hub DEBUG] Chunk {i + 1} failed, creating FAKE embedding')
                        fake_embedding = [0.0] * 768
                        processed_data.append({'content': chunk_text, 'vector': fake_embedding})
                    else:
                        processed_data.append(result)
            else:
                processed_data = []
                for i, result in enumerate(results):
                    if result is not None:
                        processed_data.append(result)
                    else:
                        failed_chunk_indices.append(i)
            failed_count = len(failed_chunk_indices)
            if failed_count > 0:
                logger.warning(f'⚠️ [AI Hub] {failed_count} chunks failed to embed: indices {failed_chunk_indices}')
            logger.info(f'📊 [AI Hub] Embedding complete: {len(processed_data)}/{len(chunks)} chunks successful')
            self.task_store.update_task(task_id, progress=90)
            summary = None
            classification = None
            debug_mode = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
            if enable_summary and (not debug_mode):
                logger.info(f'📝 [AI Hub] Generating summary for {original_name}...')
                summary = await gemini_client.summarize_text(text)
            elif enable_summary and debug_mode:
                logger.warning(f'⚠️ [AI Hub DEBUG] Skipping summary generation (DEBUG_MODE enabled)')
                summary = '[DEBUG MODE] Summary generation skipped to avoid quota errors'
            if enable_classification and (not debug_mode):
                logger.info(f'🏷️ [AI Hub] Classifying {original_name}...')
                classification = await gemini_client.classify_text(text)
            elif enable_classification and debug_mode:
                logger.warning(f'⚠️ [AI Hub DEBUG] Skipping classification (DEBUG_MODE enabled)')
                classification = {'category': 'DEBUG', 'confidence': 1.0}
            final_status = 'completed' if failed_count == 0 else 'partial_success'
            result_data = {'task_id': task_id, 'status': final_status, 'filename': original_name, 'total_chunks': len(chunks), 'successful_chunks': len(processed_data), 'failed_chunks': failed_count, 'failed_chunk_indices': failed_chunk_indices, 'data': processed_data, 'text_full': text, 'summary': summary, 'classification': classification, 'metadata': metadata or {}}
            logger.info(f'✅ [AI Hub] Task {task_id} vectorized successfully (Stateless)')
            self.task_store.update_task(task_id, status='completed', result=result_data, progress=100)
            if webhook_url:
                await self._call_webhook(webhook_url, result_data)
        except Exception as e:
            logger.error(f'❌ [AI Hub] Task {task_id} failed: {e}')
            if webhook_url:
                await self._call_webhook(webhook_url, {'task_id': task_id, 'status': 'failed', 'error': str(e), 'filename': original_name})
            self.task_store.update_task(task_id, status='failed', result={'error': str(e)}, progress=100)
        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f'🗑️ [AI Hub] Cleaned up temporary file: {file_path}')
                except Exception as ce:
                    logger.error(f'⚠️ Failed to cleanup {file_path}: {ce}')

    async def _call_webhook(self, url: str, data: Dict[str, Any]):
        original_url = url
        if url and '://' not in url:
            if url.startswith('http:/') and (not url.startswith('http://')):
                url = url.replace('http:/', 'http://', 1)
                logger.warning(f'🔧 [AI Hub] Fixed malformed URL: {url}')
            elif url.startswith('https:/') and (not url.startswith('https://')):
                url = url.replace('https:/', 'https://', 1)
                logger.warning(f'🔧 [AI Hub] Fixed malformed URL: {url}')
        if config.WEBHOOK_DOMAIN_MAPPING:
            logger.info(f'🔍 [AI Hub] Checking URL mapping for: {url}')
            for internal_host, target_domain in config.WEBHOOK_DOMAIN_MAPPING.items():
                if f'://{internal_host}/' in url or url.endswith(f'://{internal_host}'):
                    url = url.replace(f'http://{internal_host}', target_domain)
                    logger.warning(f"🔧 [AI Hub] Mapped '{internal_host}' -> '{target_domain}'")
                    logger.warning(f'   Original: {original_url}')
                    logger.warning(f'   Result:   {url}')
                    break
                elif f'://{internal_host}:' in url:
                    search_pattern = f'://{internal_host}'
                    if search_pattern in url:
                        url = url.replace(f'http://{internal_host}', target_domain)
                        logger.warning(f"🔧 [AI Hub] Mapped '{internal_host}' -> '{target_domain}' (with port)")
                        logger.warning(f'   Original: {original_url}')
                        logger.warning(f'   Result:   {url}')
                        break
        last_exception = None
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f'🔗 [AI Hub] Calling webhook: {url} (Attempt {attempt + 1}/{max_retries})')
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=data, timeout=60.0)
                    if response.status_code >= 200 and response.status_code < 300:
                        logger.info(f'✅ Webhook Success [{response.status_code}]')
                        return
                    else:
                        logger.warning(f'⚠️ Webhook returned error [{response.status_code}]: {response.text[:200]}')
            except Exception as e:
                last_exception = e
                logger.error(f'❌ Webhook attempt {attempt + 1} failed: {e}')
            if attempt < max_retries - 1:
                wait_time = 2 * 2 ** attempt
                logger.info(f'⏳ Waiting {wait_time}s before retry...')
                await asyncio.sleep(wait_time)
        logger.error(f"⛔ Webhook failed after {max_retries} attempts for Task {data.get('task_id')}: {last_exception}")
ai_hub_service = AIHubService()