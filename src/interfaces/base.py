from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class STTProvider(ABC):

    @abstractmethod
    async def transcribe(self, audio_path: str, language: str='vi') -> Dict[str, Any]:
        pass

class BaseProcessor(ABC):

    @abstractmethod
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass

class NotificationProvider(ABC):

    @abstractmethod
    async def send_message(self, message: str, attachment: Optional[str]=None) -> bool:
        pass

    @abstractmethod
    async def notify_error(self, error_msg: str, context: Optional[Dict]=None) -> bool:
        pass