import asyncio
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.processors.audio.tts_providers import EdgeTTSProvider

async def verify_edge_tts():
    print('🚀 Bắt đầu kiểm tra Edge TTS Provider...')
    provider = EdgeTTSProvider()
    test_text = 'Chào anh, em là Hoài My. Đây là giọng đọc mềm mại của Microsoft Edge TTS đã được tích hợp vào hệ thống STT-Nova2.'
    output_path = 'tests/test_edge_output.wav'
    print(f'📝 Nội dung: {test_text}')
    print('⏳ Đang tổng hợp âm thanh...')
    success = await provider.synthesize(test_text, output_path, options={'voice': 'vi-VN-HoaiMyNeural', 'rate': '+0%'})
    if success and os.path.exists(output_path):
        print(f'✅ Thành công! File đã lưu tại: {output_path}')
        print(f'📏 Kích thước file: {os.path.getsize(output_path)} bytes')
    else:
        print('❌ Thất bại: Không tạo được file âm thanh.')
if __name__ == '__main__':
    asyncio.run(verify_edge_tts())