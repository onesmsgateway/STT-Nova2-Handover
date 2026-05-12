from typing import Dict, Any, Optional
from src.core.logger import setup_logger
from src.processors.audio.tts_providers import CoquiTTSProvider, OpenAITTSProvider, ValtecTTSProvider, VieNeuTTSProvider, EdgeTTSProvider
logger = setup_logger(__name__)

class TTSService:

    def __init__(self, provider_type: str='edge'):
        self.provider_type = provider_type
        self.providers = {}

    def _get_provider(self, p_type: Optional[str]=None):
        target_type = p_type or self.provider_type
        if target_type in self.providers:
            return self.providers[target_type]
        if target_type == 'openai':
            self.providers[target_type] = OpenAITTSProvider()
        elif target_type == 'coqui':
            self.providers[target_type] = CoquiTTSProvider()
        elif target_type == 'vieneu':
            self.providers[target_type] = VieNeuTTSProvider()
        elif target_type == 'edge':
            self.providers[target_type] = EdgeTTSProvider()
        else:
            self.providers[target_type] = ValtecTTSProvider()
        return self.providers[target_type]

    async def speak(self, text: str, output_path: str, options: Dict[str, Any]=None, **kwargs) -> bool:
        p_type = kwargs.get('provider') or self.provider_type
        provider = self._get_provider(p_type)
        opts = options or {}
        opts.update(kwargs)
        result = await provider.synthesize(text, output_path, opts)
        if not result and self.provider_type == 'valtec':
            logger.warning('Valtec TTS failed or not installed. Falling back to Coqui TTS.')
            self.provider_type = 'coqui'
            self.provider = CoquiTTSProvider()
            return await self.provider.synthesize(text, output_path, opts)
        return result

    async def clone_voice(self, reference_path: str, text: str, output_path: str, ref_text: str=None, options: Dict[str, Any]=None) -> bool:
        p_type = (options or {}).get('provider') or self.provider_type
        provider = self._get_provider(p_type)
        if hasattr(provider, 'clone_voice'):
            if self.provider_type == 'vieneu':
                return await provider.clone_voice(reference_path, text, output_path, ref_text)
            return await provider.clone_voice(reference_path, text, output_path)
        if self.provider_type != 'coqui':
            logger.info(f'Provider {self.provider_type} does not support cloning. Falling back to Coqui.')
            try:
                coqui_provider = CoquiTTSProvider()
                if hasattr(coqui_provider, 'clone_voice'):
                    return await coqui_provider.clone_voice(reference_path, text, output_path)
            except Exception as e:
                logger.error(f'Fallback cloning failed: {e}')
        logger.error(f'Provider {self.provider_type} does not support voice cloning')
        return False