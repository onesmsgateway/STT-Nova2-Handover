import asyncio
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.services.pipeline_service import PipelineService

async def reproduce_error():
    print('🚀 Bắt đầu giả lập yêu cầu TTS...')
    pipeline = PipelineService()
    await pipeline.initialize()
    text = 'Thử nghiệm hệ thống hybrid tts mới.'
    voice = 'vi-VN-HoaiMyNeural'
    try:
        print(f'⏳ Đang gọi pipeline.tts_speak...')
        output_path = await pipeline.tts_speak(text, 'vi', voice=voice)
        if output_path:
            print(f'✅ Thành công: {output_path}')
        else:
            print('❌ Thất bại: tts_speak trả về None')
    except Exception as e:
        print(f'💥 Lỗi nghiêm trọng: {e}')
        import traceback
        traceback.print_exc()
if __name__ == '__main__':
    asyncio.run(reproduce_error())