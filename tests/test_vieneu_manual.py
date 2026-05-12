import asyncio
import os
import sys
sys.path.append(os.getcwd())
from src.services.tts_service import TTSService
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

async def test():
    print('🚀 Testing VieNeu-TTS Provider inside Docker...')
    try:
        service = TTSService(provider_type='vieneu')
        print('   Initializing provider...')
        service._get_provider()
        if not service.provider or not service.provider.model:
            print('❌ Model failed to load!')
            return
        print('✅ Model loaded successfully!')
        print('🗣️ Testing Speak...')
        await service.speak('Xin chào, đây là giọng đọc thử nghiệm từ VieNeu-TTS.', 'static/test_vieneu_speak.wav')
        print('✅ Speak done -> static/test_vieneu_speak.wav')
        print('🧬 Testing Clone...')
        ref_path = 'tests/test_ref.wav'
        if not os.path.exists(ref_path):
            import soundfile as sf
            import numpy as np
            print('   Creating dummy reference audio...')
            dummy_wav = np.random.uniform(-0.5, 0.5, 16000 * 3)
            sf.write(ref_path, dummy_wav, 16000)
        await service.clone_voice(ref_path, 'Tôi đang thử giọng nhân bản.', 'static/test_vieneu_clone.wav', ref_text='Đây là âm thanh mẫu')
        print('✅ Clone done -> static/test_vieneu_clone.wav')
        print('🧬 Testing Long-form Clone...')
        long_text = 'Hôm nay tôi muốn giới thiệu về hệ thống STT-Nova 2. Đây là một hệ thống tích hợp công nghệ trí tuệ nhân tạo tiên tiến nhất hiện nay cho việc chuyển đổi giọng nói và tổng hợp âm thanh tiếng Việt. Với VieNeu-TTS, chất lượng giọng nói đã đạt đến độ tự nhiên cao, gần giống với con người nhất. Chúng tôi hy vọng hệ thống này sẽ giúp ích cho nhiều người trong việc tạo ra nội dung âm thanh chất lượng cao một cách nhanh chóng và hiệu quả. Ngoài ra, tính năng nhân bản giọng nói cũng là một bước đột phá quan trọng.'
        await service.clone_voice(ref_path, long_text, 'static/test_vieneu_long_clone.wav', ref_text='Đây là âm thanh mẫu')
        print('✅ Long Clone done -> static/test_vieneu_long_clone.wav')
    except Exception as e:
        print(f'❌ Error: {e}')
        import traceback
        traceback.print_exc()
if __name__ == '__main__':
    asyncio.run(test())