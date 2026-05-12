import json
import os
import time
import threading
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
import logging
from config import URL_DELAY, QUEUE_FILE, STATUS_FILE, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY, TELEGRAM_BOT_ENABLED, TELEGRAM_ADMIN_CHAT_ID, DEBUG_MODE, AUDIO_PROCESSING_MODE, IN_PROGRESS_FILE, DEAD_LETTER_FILE, AUTO_RESUME_QUEUE
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueueManager:

    def __init__(self, telegram_bot=None):
        self.telegram_bot = telegram_bot
        self.processing = False
        self.current_processing_item = None
        self.lock = threading.RLock()
        self.processing_thread = None
        self._init_files()

    def _send_telegram_message(self, message: str):
        if self.telegram_bot and TELEGRAM_BOT_ENABLED:
            try:

                def send_telegram():
                    try:
                        asyncio.run(self._send_telegram_async(message))
                    except Exception as e:
                        logger.error(f'Lỗi gửi Telegram: {e}')
                telegram_thread = threading.Thread(target=send_telegram, daemon=True)
                telegram_thread.start()
            except Exception as e:
                logger.error(f'Lỗi khi gửi thông báo Telegram: {e}')
        else:
            logger.info(f'Telegram message (disabled): {message}')

    async def _send_telegram_async(self, message: str):
        try:
            from telegram_bot import TelegramBot
            async with TelegramBot() as bot:
                await bot.send_admin_message(message)
        except Exception as e:
            logger.error(f'Lỗi gửi Telegram async: {e}')

    def _init_files(self):
        os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
        if not os.path.exists(QUEUE_FILE):
            with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
                f.write('[]')
        if not os.path.exists(STATUS_FILE):
            self._save_status({'total_processed': 0, 'total_failed': 0, 'last_processed_time': None, 'is_processing': False})
        if not os.path.exists(IN_PROGRESS_FILE):
            with open(IN_PROGRESS_FILE, 'w', encoding='utf-8') as f:
                f.write('[]')
        if not os.path.exists(DEAD_LETTER_FILE):
            with open(DEAD_LETTER_FILE, 'w', encoding='utf-8') as f:
                f.write('[]')
        self._recover_in_progress_items()

    def _recover_in_progress_items(self):
        try:
            with open(IN_PROGRESS_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content or content == '[]':
                    return
                in_progress_items = json.loads(content)
            if in_progress_items:
                logger.warning(f'🔄 CRASH RECOVERY: Tìm thấy {len(in_progress_items)} items đang xử lý dở')
                for item in in_progress_items:
                    item['retry_count'] = item.get('retry_count', 0) + 1
                    item['recovered_at'] = datetime.now().isoformat()
                    logger.info(f"   ↩️ Recovering: {item.get('url', 'unknown')[:50]}... (retry #{item['retry_count']})")
                existing_queue = self._read_queue()
                new_queue = in_progress_items + existing_queue
                self._write_queue(new_queue)
                self._clear_in_progress()
                logger.info(f'✅ Đã recover {len(in_progress_items)} items vào queue')
                self._send_telegram_message(f'🔄 CRASH RECOVERY: Đã khôi phục {len(in_progress_items)} items vào hàng đợi')
        except Exception as e:
            logger.error(f'❌ Lỗi khi recover in-progress items: {e}')

    def _save_in_progress(self, item: Dict):
        try:
            with open(IN_PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump([item], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f'Lỗi khi lưu in-progress: {e}')

    def _clear_in_progress(self):
        try:
            with open(IN_PROGRESS_FILE, 'w', encoding='utf-8') as f:
                f.write('[]')
        except Exception as e:
            logger.error(f'Lỗi khi xóa in-progress: {e}')

    def _move_to_dead_letter(self, item: Dict, error: str):
        try:
            dead_letter = []
            if os.path.exists(DEAD_LETTER_FILE):
                with open(DEAD_LETTER_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        dead_letter = json.loads(content)
            item['error'] = error
            item['failed_at'] = datetime.now().isoformat()
            item['id'] = item.get('task_id') or str(hash(item.get('url', '')))[:8]
            dead_letter.append(item)
            with open(DEAD_LETTER_FILE, 'w', encoding='utf-8') as f:
                json.dump(dead_letter, f, indent=2, ensure_ascii=False)
            logger.warning(f"💀 Đã chuyển item vào dead letter queue: {item.get('url', 'unknown')[:50]}...")
            self._send_telegram_message(f"💀 Dead Letter: {item.get('url', 'unknown')[:50]}...\nLỗi: {error[:100]}")
        except Exception as e:
            logger.error(f'Lỗi khi chuyển vào dead letter: {e}')

    def get_dead_letter_queue(self) -> List[Dict]:
        try:
            if os.path.exists(DEAD_LETTER_FILE):
                with open(DEAD_LETTER_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
        except Exception as e:
            logger.error(f'Lỗi khi đọc dead letter queue: {e}')
        return []

    def retry_dead_letter_item(self, item_id: str) -> bool:
        try:
            dead_letter = self.get_dead_letter_queue()
            item_to_retry = None
            remaining = []
            for item in dead_letter:
                if item.get('id') == item_id:
                    item_to_retry = item
                else:
                    remaining.append(item)
            if not item_to_retry:
                return False
            item_to_retry['retry_count'] = 0
            item_to_retry.pop('error', None)
            item_to_retry.pop('failed_at', None)
            item_to_retry['retried_from_dead_letter'] = datetime.now().isoformat()
            existing_queue = self._read_queue()
            existing_queue.append(item_to_retry)
            self._write_queue(existing_queue)
            with open(DEAD_LETTER_FILE, 'w', encoding='utf-8') as f:
                json.dump(remaining, f, indent=2, ensure_ascii=False)
            logger.info(f'♻️ Đã retry item từ dead letter: {item_id}')
            return True
        except Exception as e:
            logger.error(f'Lỗi khi retry dead letter item: {e}')
            return False

    def clear_dead_letter_item(self, item_id: str) -> bool:
        try:
            dead_letter = self.get_dead_letter_queue()
            remaining = [item for item in dead_letter if item.get('id') != item_id]
            if len(remaining) == len(dead_letter):
                return False
            with open(DEAD_LETTER_FILE, 'w', encoding='utf-8') as f:
                json.dump(remaining, f, indent=2, ensure_ascii=False)
            logger.info(f'🗑️ Đã xóa item khỏi dead letter: {item_id}')
            return True
        except Exception as e:
            logger.error(f'Lỗi khi xóa dead letter item: {e}')
            return False

    def _save_status(self, status: Dict):
        try:
            with open(STATUS_FILE, 'w', encoding='utf-8') as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f'Lỗi khi lưu status: {e}')

    def _load_status(self) -> Dict:
        try:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
        except Exception as e:
            logger.error(f'Lỗi khi load status: {e}')
        default_status = {'total_processed': 0, 'total_failed': 0, 'last_processed_time': None, 'is_processing': False}
        self._save_status(default_status)
        return default_status

    def add_urls(self, urls: List[str], audio_processing_mode: str=None, options: Dict=None) -> Dict:
        try:
            with self.lock:
                existing_queue = self._read_queue()
                existing_urls = {item['url'] for item in existing_queue}
                current_processing_url = self._get_current_processing_url()
                if current_processing_url:
                    existing_urls.add(current_processing_url)
                new_items = []
                duplicate_count = 0
                for url in urls:
                    if url in existing_urls:
                        duplicate_count += 1
                        if DEBUG_MODE:
                            logger.info(f'Skip duplicate URL: {url}')
                    else:
                        new_items.append({'url': url, 'audio_processing_mode': audio_processing_mode, 'task_id': options.get('task_id') if options else None, 'callback_url': options.get('callback_url') if options else None, 'added_time': datetime.now().isoformat()})
                        existing_urls.add(url)
                new_queue = existing_queue + new_items
                self._write_queue(new_queue)
                total_items = len(new_queue)
                added_count = len(new_items)
                if DEBUG_MODE:
                    logger.info(f'Đã thêm {added_count} URLs vào queue (skip {duplicate_count} duplicates). Tổng: {total_items}')
                else:
                    logger.info(f'Đã thêm {added_count} URLs vào queue. Tổng: {total_items}')
                message = f'📥 Đã nhận {added_count} URLs mới\n📊 Tổng queue: {total_items} URLs'
                self._send_telegram_message(message)
                return {'success': True, 'added': added_count, 'duplicate_count': duplicate_count, 'total_in_queue': total_items, 'message': f'Đã thêm {added_count} URLs vào queue'}
        except Exception as e:
            logger.error(f'Lỗi khi thêm URLs: {e}')
            return {'success': False, 'error': str(e), 'message': f'Lỗi khi thêm URLs: {e}'}

    def _get_current_processing_url(self) -> Optional[str]:
        with self.lock:
            if self.current_processing_item:
                return self.current_processing_item.get('url')
        return None

    def _read_queue(self) -> List[Dict]:
        try:
            with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
                return []
        except json.JSONDecodeError as e:
            logger.error(f'Lỗi JSON khi đọc queue: {e}')
            self._write_queue([])
            return []
        except Exception as e:
            logger.error(f'Lỗi khi đọc queue: {e}')
            return []

    def _write_queue(self, queue: List[Dict]):
        try:
            with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f'Lỗi khi ghi queue: {e}')

    def _read_urls(self) -> List[str]:
        queue = self._read_queue()
        return [item.get('url', '') for item in queue if item.get('url')]

    def _remove_processed_urls(self, processed_urls: List[str]):
        try:
            with self.lock:
                current_queue = self._read_queue()
                remaining_queue = []
                removed_count = 0
                for item in current_queue:
                    if removed_count < len(processed_urls) and item.get('url') in processed_urls:
                        removed_count += 1
                        logger.info(f"Đã xóa URL: {item.get('url')}")
                    else:
                        remaining_queue.append(item)
                self._write_queue(remaining_queue)
                logger.info(f'Đã xóa {removed_count} URLs đã xử lý. Còn lại: {len(remaining_queue)}')
        except Exception as e:
            logger.error(f'Lỗi khi xóa URLs đã xử lý: {e}')

    def get_queue_status(self) -> Dict:
        try:
            urls = self._read_urls()
            status = self._load_status()
            return {'queue_length': len(urls), 'is_processing': self.processing, 'total_processed': status.get('total_processed', 0), 'total_failed': status.get('total_failed', 0), 'current_batch': 0, 'last_processed_time': status.get('last_processed_time'), 'batch_size': 1, 'max_workers': 1}
        except Exception as e:
            logger.error(f'Lỗi khi lấy queue status: {e}')
            return {'error': str(e)}

    def start_processing(self, processor_func):
        if self.processing:
            logger.warning('Queue đang được xử lý')
            return False
        self.processing = True
        self.processing_thread = threading.Thread(target=self._process_queue_loop, args=(processor_func,), daemon=True)
        self.processing_thread.start()
        logger.info('Đã bắt đầu xử lý queue')
        message = '🚀 Bắt đầu xử lý queue URLs'
        self._send_telegram_message(message)
        return True

    def stop_processing(self):
        self.processing = False
        logger.info('Đã dừng xử lý queue')
        message = '⏹️ Đã dừng xử lý queue'
        self._send_telegram_message(message)

    def _process_queue_loop(self, processor_func):
        status = self._load_status()
        status['session_processed'] = 0
        status['session_failed'] = 0
        status['is_processing'] = True
        self._save_status(status)
        try:
            while self.processing:
                queue = self._read_queue()
                if not queue:
                    logger.info('Queue trống, dừng xử lý')
                    break
                current_item = queue[0]
                with self.lock:
                    self.current_processing_item = current_item
                current_url = current_item.get('url', '')
                audio_processing_mode = current_item.get('audio_processing_mode', AUDIO_PROCESSING_MODE)
                logger.info(f'Xử lý URL: {current_url}')
                result = self._process_single_url(current_item, processor_func)
                with self.lock:
                    self.current_processing_item = None
                if result['success']:
                    status['total_processed'] += 1
                    status['session_processed'] += 1
                    try:
                        from stats_manager import stats_manager
                        stats_manager.increment_processed(1)
                    except Exception as e:
                        logger.warning(f'Không thể cập nhật global stats: {e}')
                else:
                    status['total_failed'] += 1
                    status['session_failed'] += 1
                    try:
                        from stats_manager import stats_manager
                        stats_manager.increment_failed(1)
                    except Exception as e:
                        logger.warning(f'Không thể cập nhật global stats: {e}')
                status['last_processed_time'] = datetime.now().isoformat()
                self._save_status(status)
                self._remove_processed_urls([current_url])
                remaining_queue = self._read_queue()
                if self.processing and len(remaining_queue) > 0:
                    time.sleep(URL_DELAY)
        except Exception as e:
            logger.error(f'Lỗi trong queue processing: {e}')
            message = f'❌ Lỗi trong queue processing: {e}'
            self._send_telegram_message(message)
        finally:
            session_processed = status.get('session_processed', 0)
            session_failed = status.get('session_failed', 0)
            self.processing = False
            status['is_processing'] = False
            self._save_status(status)
            final_status = self.get_queue_status()
            message = f"🎉 Hoàn thành xử lý queue\n📊 Phiên này: {session_processed} xử lý, {session_failed} lỗi\n📈 Tổng tích lũy: {final_status['total_processed']} xử lý, {final_status['total_failed']} lỗi"
            self._send_telegram_message(message)

    def _process_single_url(self, item: Dict, processor_func) -> Dict:
        url = item.get('url')
        audio_processing_mode = item.get('audio_processing_mode')
        task_id = item.get('task_id')
        callback_url = item.get('callback_url')
        retry_count = item.get('retry_count', 0)
        consecutive_failures = 0
        self._save_in_progress(item)
        for attempt in range(MAX_RETRIES):
            try:
                if DEBUG_MODE:
                    if attempt == 0:
                        logger.info(f'🔄 Xử lý URL: {url} (attempt {attempt + 1}/{MAX_RETRIES}, total retry: {retry_count})')
                    else:
                        logger.info(f'🔄 Retry URL: {url} (attempt {attempt + 1}/{MAX_RETRIES})')
                result = processor_func(url, audio_processing_mode, task_id=task_id, callback_url=callback_url)
                consecutive_failures = 0
                if DEBUG_MODE:
                    logger.info(f'✅ Thành công xử lý URL: {url} (attempt {attempt + 1})')
                self._clear_in_progress()
                return result
            except Exception as e:
                consecutive_failures += 1
                logger.error(f'❌ Lỗi attempt {attempt + 1}/{MAX_RETRIES} cho {url}: {e}')
                if consecutive_failures >= 2:
                    logger.error(f'🚫 Circuit breaker: Quá nhiều lỗi liên tiếp ({consecutive_failures}), dừng retry')
                    error_msg = f'Circuit breaker: Quá nhiều lỗi liên tiếp ({consecutive_failures})'
                    total_retries = retry_count + attempt + 1
                    if total_retries >= MAX_RETRIES * 2:
                        self._move_to_dead_letter(item, error_msg)
                    self._clear_in_progress()
                    return {'url': url, 'success': False, 'error': error_msg}
                if attempt < MAX_RETRIES - 1:
                    if DEBUG_MODE:
                        logger.info(f'⏳ Chờ {RETRY_DELAY}s trước khi retry...')
                    time.sleep(RETRY_DELAY)
                else:
                    error_msg = f'Thất bại sau {MAX_RETRIES} attempts: {e}'
                    logger.error(f'💥 Thất bại hoàn toàn sau {MAX_RETRIES} attempts cho {url}')
                    total_retries = retry_count + MAX_RETRIES
                    if total_retries >= MAX_RETRIES * 2:
                        self._move_to_dead_letter(item, error_msg)
                    self._clear_in_progress()
                    return {'url': url, 'success': False, 'error': error_msg}

    def resume_processing(self, processor_func):
        status = self._load_status()
        urls = self._read_urls()
        if urls:
            logger.info(f'Tiếp tục xử lý {len(urls)} URLs còn lại')
            message = f'🔄 Tiếp tục xử lý sau restart\n📥 Còn lại: {len(urls)} URLs'
            self._send_telegram_message(message)
            return self.start_processing(processor_func)
        return False

    def cleanup(self):
        self.stop_processing()
        logger.info('Đã cleanup queue manager')