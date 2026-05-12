import asyncio
import os
import sys
import logging
import numpy as np
import soundfile as sf
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
sys.path.append(os.path.abspath('src'))
from processors.audio.tts_providers import VieNeuTTSProvider

async def main():
    provider = VieNeuTTSProvider()
    logger.info('Initializing provider...')
    await provider.synthesize('Xin chào. Phút này tôi đang kiểm tra chất lượng giọng đọc.', 'static/quality_test.wav')
    if os.path.exists('static/quality_test.wav'):
        size = os.path.getsize('static/quality_test.wav')
        logger.info(f'Generated test file: static/quality_test.wav (Size: {size} bytes)')
        if size > 10000:
            logger.info('✅ Quality test file seems valid.')
        else:
            logger.error('❌ Quality test file is too small.')
    else:
        logger.error('❌ Failed to generate quality test file.')
if __name__ == '__main__':
    asyncio.run(main())