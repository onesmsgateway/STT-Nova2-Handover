import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
import aiohttp
from telegram_bot import TelegramBot
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_ENABLED, TELEGRAM_ADMIN_CHAT_ID
logger = logging.getLogger(__name__)

class TelegramHandler:

    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.base_url = f'https://api.telegram.org/bot{self.token}'
        self.enabled = TELEGRAM_BOT_ENABLED
        self.session = None
        self.last_update_id = 0

    async def __aenter__(self):
        if self.enabled:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def cleanup(self):
        pass

    def stop(self):
        self.enabled = False
        if hasattr(self, '_polling_task') and self._polling_task:
            self._polling_task.cancel()

    async def get_updates(self) -> list:
        if not self.enabled:
            return []
        try:
            url = f'{self.base_url}/getUpdates'
            params = {'offset': self.last_update_id + 1, 'timeout': 30}
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok'):
                            updates = data.get('result', [])
                            if updates:
                                self.last_update_id = updates[-1]['update_id']
                            return updates
                    return []
        except asyncio.TimeoutError:
            logger.warning('Telegram API timeout - retrying next cycle')
            return []
        except Exception as e:
            logger.error(f'Error getting updates: {e}', exc_info=True)
            return []

    async def send_message(self, chat_id: int, text: str, parse_mode: str='HTML', reply_markup: Optional[Dict]=None) -> bool:
        if not self.enabled:
            return False
        try:
            url = f'{self.base_url}/sendMessage'
            data = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
            if reply_markup:
                data['reply_markup'] = reply_markup
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f'Error sending message: {e}')
            return False

    async def handle_command(self, chat_id: int, command: str, username: str='') -> bool:
        try:
            clean_command = command.split('@')[0].lower()
            if clean_command == '/start':
                return await self.handle_start_command(chat_id, username)
            elif clean_command == '/stt_status':
                return await self.handle_status_command(chat_id)
            elif clean_command == '/stt_restart':
                return await self.handle_restart_command(chat_id)
            elif clean_command == '/stt_help':
                return await self.handle_help_command(chat_id)
            else:
                logger.debug(f'Bỏ qua command không xác định: {command}')
                return True
        except Exception as e:
            logger.error(f'Error handling command {command}: {e}')
            return await self.send_message(chat_id, f'❌ Lỗi xử lý command: {str(e)}')

    async def handle_start_command(self, chat_id: int, username: str) -> bool:
        welcome_text = f"\n🚀 <b>Chào mừng đến với STT-Nova2 Bot!</b>\n\n👋 <b>Xin chào</b> {(username if username else 'Admin')}\n\n🤖 <b>Bot này giúp bạn:</b>\n• 📊 Kiểm tra trạng thái service\n• 🔄 Khởi động lại service\n• ⚠️ Nhận thông báo lỗi\n• 🚀 Nhận thông báo khởi động\n\n📝 <b>Các lệnh có sẵn:</b>\n/stt_status - Kiểm tra trạng thái service\n/stt_restart - Khởi động lại service\n/stt_help - Xem hướng dẫn\n\n⏰ <b>Thời gian:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n        "
        keyboard = {'inline_keyboard': [[{'text': '📊 Trạng thái Service', 'callback_data': 'status'}, {'text': '🔄 Khởi động lại', 'callback_data': 'restart'}], [{'text': '❓ Trợ giúp', 'callback_data': 'help'}]]}
        return await self.send_message(chat_id, welcome_text, reply_markup=keyboard)

    async def handle_status_command(self, chat_id: int) -> bool:
        try:
            await self.send_message(chat_id, '🔍 Đang kiểm tra trạng thái service...')
            from telegram_bot import TelegramBot
            bot = TelegramBot()
            await bot.__aenter__()
            status = await bot.get_service_status()
            from stats_manager import stats_manager
            stats = stats_manager.get_all_stats()
            queue_stats = {}
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:8000/queue/status') as response:
                        if response.status == 200:
                            queue_data = await response.json()
                            queue_stats = {'queue_length': queue_data.get('queue_length', 0), 'is_processing': queue_data.get('is_processing', False), 'session_processed': queue_data.get('total_processed', 0), 'session_failed': queue_data.get('total_failed', 0)}
            except Exception as e:
                logger.warning(f'Không thể lấy queue stats: {e}')
                queue_stats = {'queue_length': 0, 'is_processing': False, 'session_processed': 0, 'session_failed': 0}
            await bot.__aexit__(None, None, None)
            if status.get('status') == 'error':
                text = f"\n❌ <b>Lỗi kiểm tra trạng thái</b>\n\n🚨 <b>Error:</b> {status.get('message', 'Unknown error')}\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n                "
            else:
                today_processed = stats.get('today_processed', 0)
                today_failed = stats.get('today_failed', 0)
                total_processed = stats.get('total_processed', 0)
                total_failed = stats.get('total_failed', 0)
                queue_status = '🟢 Đang xử lý' if queue_stats.get('is_processing') else '⏸️ Dừng'
                queue_length = queue_stats.get('queue_length', 0)
                error_notification = ''
                if today_failed > 0:
                    error_notification = f'\n⚠️ <b>Có {today_failed} lỗi hôm nay - Kiểm tra logs để xem chi tiết</b>'
                text = f"\n📊 <b>Trạng thái STT-Nova2 Service</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🟢 <b>Status:</b> {status['status'].title()}\n🆔 <b>PID:</b> {status['pid']}\n💾 <b>Memory:</b> {status['memory_mb']} MB\n🖥️ <b>CPU:</b> {status['cpu_percent']}%\n🧠 <b>System Memory:</b> {status['system_memory_percent']}%\n💿 <b>Disk Usage:</b> {status['disk_usage_percent']}%\n⏱️ <b>Uptime:</b> {status['uptime']}\n\n📈 <b>Thống kê xử lý:</b>\n📅 <b>Hôm nay:</b> {today_processed} xử lý, {today_failed} lỗi{error_notification}\n📊 <b>Tổng tích lũy:</b> {total_processed} xử lý, {total_failed} lỗi\n\n🔄 <b>Queue hiện tại:</b>\n📥 <b>Queue:</b> {queue_length} URLs\n⚡ <b>Status:</b> {queue_status}\n                "
            return await self.send_message(chat_id, text)
        except Exception as e:
            logger.error(f'Error in handle_status_command: {e}')
            return await self.send_message(chat_id, f'❌ Lỗi kiểm tra trạng thái: {str(e)}')

    async def handle_restart_command(self, chat_id: int) -> bool:
        try:
            await self.send_message(chat_id, '🔄 Đang khởi động lại service components...')
            import os
            is_container = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER') == 'true'
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post('http://localhost:8000/service/restart') as response:
                        if response.status == 200:
                            result = await response.json()
                            restart_text = f"\n🔄 <b>Service Components Restart</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n✅ <b>Status:</b> Restart command đã được thực hiện\n\n📋 <b>Kết quả:</b>\n💡 Môi trường: {('Container' if is_container else 'Host')}\n✅ Service components restart API called\n📊 Status: {result.get('status', 'unknown')}\n📝 Message: {result.get('message', 'No message')}\n\n⏳ <b>Lưu ý:</b> Service components sẽ restart trong vài giây\n🔔 <b>Thông báo:</b> Bạn sẽ nhận được restart notification\n                            "
                            await self.send_message(chat_id, restart_text)
                            import asyncio
                            await asyncio.sleep(3)
                            ready_text = f"\n✅ <b>Service đã sẵn sàng nhận requests!</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🟢 <b>Status:</b> Tất cả components đã được khởi tạo lại\n📊 <b>Components:</b> Telegram Bot, Queue Manager, Audio Processor\n\n🚀 <b>Service ready to process audio requests!</b>\n                            "
                            return await self.send_message(chat_id, ready_text)
                        else:
                            error_text = await response.text()
                            text = f"\n❌ <b>Không thể restart Service Components</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🚨 <b>Status:</b> API restart thất bại\n📊 <b>HTTP Status:</b> {response.status}\n📝 <b>Error:</b> {error_text[:100]}...\n\n🔧 <b>Hướng dẫn thủ công:</b>\n• <b>Container:</b> `docker restart stt-nova2-service`\n• <b>Docker Compose:</b> `docker-compose restart stt-nova2`\n• <b>Host:</b> `systemctl restart stt-nova2`\n\n💡 <b>Lưu ý:</b> API restart chỉ restart components, không restart container\n                            "
                            return await self.send_message(chat_id, text)
            except Exception as e:
                text = f"\n❌ <b>Lỗi restart Service Components</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🚨 <b>Error:</b> {str(e)}\n\n🔧 <b>Hướng dẫn thủ công:</b>\n• <b>Container:</b> `docker restart stt-nova2-service`\n• <b>Docker Compose:</b> `docker-compose restart stt-nova2`\n• <b>Host:</b> `systemctl restart stt-nova2`\n\n💡 <b>Lưu ý:</b> API restart chỉ restart components, không restart container\n                "
                return await self.send_message(chat_id, text)
        except Exception as e:
            logger.error(f'Error in handle_restart_command: {e}')
            return await self.send_message(chat_id, f'❌ Lỗi restart service: {str(e)}')

    async def handle_help_command(self, chat_id: int) -> bool:
        help_text = f"\n❓ <b>Hướng dẫn sử dụng STT-Nova2 Bot</b>\n\n📋 <b>Các lệnh có sẵn:</b>\n\n/start - Khởi động bot và xem menu chính\n/stt_status - Kiểm tra trạng thái service\n/stt_restart - Hướng dẫn khởi động lại service\n/stt_help - Xem hướng dẫn này\n\n🔧 <b>Chức năng:</b>\n• 📊 <b>Monitoring:</b> Theo dõi trạng thái service\n• ⚠️ <b>Alerting:</b> Thông báo lỗi tự động\n• 🚀 <b>Startup:</b> Thông báo khi service khởi động\n• 🔄 <b>Control:</b> Điều khiển service cơ bản\n\n📞 <b>Liên hệ:</b>\nNếu có vấn đề, vui lòng liên hệ admin\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n        "
        return await self.send_message(chat_id, help_text)

    async def handle_unknown_command(self, chat_id: int, command: str) -> bool:
        text = f"\n❓ <b>Command không xác định</b>\n\n🚫 <b>Command:</b> {command}\n📝 <b>Lệnh có sẵn:</b> /start, /stt_status, /stt_restart, /stt_help\n\n💡 <b>Gợi ý:</b> Sử dụng /help để xem danh sách lệnh\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n        "
        return await self.send_message(chat_id, text)

    async def handle_callback_query(self, callback_query: Dict[str, Any]) -> bool:
        try:
            chat_id = callback_query['message']['chat']['id']
            callback_data = callback_query['data']
            if callback_data == 'status':
                return await self.handle_status_command(chat_id)
            elif callback_data == 'restart':
                return await self.handle_restart_command(chat_id)
            elif callback_data == 'help':
                return await self.handle_help_command(chat_id)
            else:
                return await self.send_message(chat_id, f'❓ Callback không xác định: {callback_data}')
        except Exception as e:
            logger.error(f'Error handling callback query: {e}')
            return False

    async def process_updates(self):
        logger.info('Bắt đầu xử lý Telegram updates...')
        while self.enabled:
            try:
                updates = await self.get_updates()
                for update in updates:
                    if 'callback_query' in update:
                        await self.handle_callback_query(update['callback_query'])
                    elif 'message' in update:
                        message = update['message']
                        chat_id = message['chat']['id']
                        if chat_id != TELEGRAM_ADMIN_CHAT_ID:
                            continue
                        username = message.get('from', {}).get('username', '')
                        if 'text' in message:
                            text = message['text']
                            if text.startswith('/'):
                                await self.handle_command(chat_id, text, username)
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info('Telegram polling task bị cancel')
                break
            except Exception as e:
                logger.error(f'Error processing updates: {e}')
                await asyncio.sleep(5)
        logger.info('Dừng xử lý Telegram updates')