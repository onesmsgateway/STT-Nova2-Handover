from typing import Optional, Dict, List
from src.interfaces.base import NotificationProvider
from src.core.logger import setup_logger
from telegram_bot import TelegramBot
logger = setup_logger(__name__)

class TelegramNotificationProvider(NotificationProvider):

    def __init__(self):
        self.bot = TelegramBot()
        self.enabled = self.bot.enabled

    async def initialize(self):
        if self.enabled:
            await self.bot.__aenter__()

    async def shutdown(self):
        if self.enabled:
            await self.bot.__aexit__(None, None, None)

    async def send_message(self, message: str, attachment: Optional[str]=None) -> bool:
        if not self.enabled:
            return False
        return await self.bot.send_admin_message(message)

    async def notify_error(self, error_msg: str, context: Optional[Dict]=None) -> bool:
        if not self.enabled:
            return False
        ctx_str = str(context) if context else ''

        class MockException(Exception):
            pass
        return await self.bot.notify_error(MockException(error_msg), ctx_str)

class NotificationService:

    def __init__(self):
        self.providers: List[NotificationProvider] = []
        tg_provider = TelegramNotificationProvider()
        self.providers.append(tg_provider)

    async def start(self):
        for p in self.providers:
            if hasattr(p, 'initialize'):
                await p.initialize()

    async def stop(self):
        for p in self.providers:
            if hasattr(p, 'shutdown'):
                await p.shutdown()

    async def notify(self, message: str):
        for p in self.providers:
            try:
                await p.send_message(message)
            except Exception as e:
                logger.error(f'Failed to send notification: {e}')

    async def notify_error(self, error: str, context: dict=None):
        for p in self.providers:
            try:
                await p.notify_error(error, context)
            except Exception as e:
                logger.error(f'Failed to send error notification: {e}')