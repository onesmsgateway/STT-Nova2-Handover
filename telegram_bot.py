import asyncio
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
import aiohttp
import json
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, TELEGRAM_BOT_ENABLED, TELEGRAM_NOTIFY_STARTUP, TELEGRAM_NOTIFY_ERRORS
logger = logging.getLogger(__name__)

class TelegramBot:

    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.admin_chat_id = TELEGRAM_ADMIN_CHAT_ID
        self.base_url = f'https://telegram.minhbv.com/bot{self.token}'
        self.enabled = TELEGRAM_BOT_ENABLED
        self.session = None

    async def __aenter__(self):
        if self.enabled:
            self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def send_message(self, chat_id: int, text: str, parse_mode: str='HTML') -> bool:
        if not self.enabled:
            return False
        try:
            url = f'{self.base_url}/sendMessage'
            data = {'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    if response.status == 200:
                        return True
                    else:
                        logger.error(f'Telegram API error: {response.status}')
                        return False
        except Exception as e:
            logger.error(f'Error sending Telegram message: {e}')
            return False

    async def send_admin_message(self, text: str, parse_mode: str='HTML') -> bool:
        if not self.admin_chat_id:
            logger.warning('Admin chat ID not set')
            return False
        return await self.send_message(self.admin_chat_id, text, parse_mode)

    async def notify_service_startup(self) -> bool:
        if not TELEGRAM_NOTIFY_STARTUP:
            return True
        text = f"\n🚀 <b>STT-Nova2 Service Started</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🌐 <b>Status:</b> Running\n📍 <b>Endpoint:</b> http://localhost:8000\n\n✅ Service đã sẵn sàng nhận requests!\n        "
        return await self.send_admin_message(text)

    async def notify_error(self, error: Exception, context: str='') -> bool:
        if not TELEGRAM_NOTIFY_ERRORS:
            return True
        error_traceback = traceback.format_exc()
        text = f"\n⚠️ <b>STT-Nova2 Service Error</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🚨 <b>Error:</b> {type(error).__name__}: {str(error)}\n📝 <b>Context:</b> {context}\n\n<code>{error_traceback[:1000]}...</code>\n        "
        return await self.send_admin_message(text)

    async def notify_processing_error(self, error_message: str, url: str='', xml_cdr_uuid: str='') -> bool:
        text = f"\n🚨 <b>Lỗi xử lý Audio</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🔗 <b>URL:</b> {url[:100]}{('...' if len(url) > 100 else '')}\n🆔 <b>CDR UUID:</b> {xml_cdr_uuid}\n❌ <b>Lỗi:</b> {error_message}\n\n💡 <b>Gợi ý:</b> Kiểm tra URL audio, kết nối mạng, hoặc API keys\n        "
        return await self.send_admin_message(text)

    async def notify_processing_start(self, request_id: str, urls_count: int) -> bool:
        text = f"\n🔄 <b>Processing Started</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🆔 <b>Request ID:</b> {request_id}\n📊 <b>URLs:</b> {urls_count} files\n⏳ <b>Status:</b> Processing...\n        "
        return await self.send_admin_message(text)

    async def notify_processing_complete(self, request_id: str, results: list) -> bool:
        success_count = sum((1 for r in results if r.get('success', False)))
        total_count = len(results)
        text = f"\n✅ <b>Processing Complete</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🆔 <b>Request ID:</b> {request_id}\n📊 <b>Results:</b> {success_count}/{total_count} successful\n🎯 <b>Status:</b> Completed\n        "
        return await self.send_admin_message(text)

    async def get_service_status(self) -> Dict[str, Any]:
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            disk_usage = psutil.disk_usage('/').percent
            create_time = process.create_time()
            current_time = datetime.now().timestamp()
            uptime_seconds = current_time - create_time
            days = int(uptime_seconds // 86400)
            hours = int(uptime_seconds % 86400 // 3600)
            minutes = int(uptime_seconds % 3600 // 60)
            seconds = int(uptime_seconds % 60)
            if days > 0:
                uptime_str = f'{days} day(s), {hours:02d}:{minutes:02d}:{seconds:02d}'
            else:
                uptime_str = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
            return {'status': 'running', 'pid': process.pid, 'memory_mb': round(memory_info.rss / 1024 / 1024, 2), 'cpu_percent': cpu_percent, 'system_memory_percent': memory_percent, 'disk_usage_percent': disk_usage, 'uptime': uptime_str}
        except Exception as e:
            logger.error(f'Error getting service status: {e}')
            return {'status': 'error', 'message': str(e)}

    async def send_service_status(self) -> bool:
        status = await self.get_service_status()
        if status.get('status') == 'error':
            text = f"\n❌ <b>Service Status Error</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🚨 <b>Error:</b> {status.get('message', 'Unknown error')}\n            "
        else:
            text = f"\n📊 <b>STT-Nova2 Service Status</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🟢 <b>Status:</b> {status['status'].title()}\n🆔 <b>PID:</b> {status['pid']}\n💾 <b>Memory:</b> {status['memory_mb']} MB\n🖥️ <b>CPU:</b> {status['cpu_percent']}%\n🧠 <b>System Memory:</b> {status['system_memory_percent']}%\n💿 <b>Disk Usage:</b> {status['disk_usage_percent']}%\n⏱️ <b>Uptime:</b> {status['uptime']}\n            "
        return await self.send_admin_message(text)

    async def restart_service(self) -> bool:
        text = f"\n🔄 <b>Service Restart Requested</b>\n\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n⚠️ <b>Note:</b> Restart functionality requires external process management\n📝 <b>Manual:</b> Please restart the service manually using your process manager\n        "
        return await self.send_admin_message(text)