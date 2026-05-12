from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class TTSProvider(ABC):

    @abstractmethod
    async def synthesize(self, text: str, output_path: str, options: Dict[str, Any]=None) -> bool:
        pass

class VoiceCloningProvider(ABC):

    @abstractmethod
    async def clone_voice(self, reference_audio_path: str, text: str, output_path: str) -> bool:
        pass