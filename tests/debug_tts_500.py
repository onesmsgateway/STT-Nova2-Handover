import asyncio
import os
import sys
import uuid
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

async def debug_tts_flow():
    print('🔍 [DEBUG] Bắt đầu kiểm tra luồng TTS...')
    try:
        from src.services.pipeline_service import PipelineService
        print('✅ [DEBUG] Import PipelineService thành công')
    except Exception as e:
        print(f'❌ [DEBUG] Lỗi import PipelineService: {e}')
        return
    try:
        pipeline = PipelineService()
        print('✅ [DEBUG] Khởi tạo PipelineService thành công')
    except Exception as e:
        print(f'❌ [DEBUG] Lỗi khi tạo instance PipelineService: {e}')
        import traceback
        traceback.print_exc()
        return
    text = 'Xin chào anh, đây là tin nhắn debug.'
    provider_type = 'edge'
    voice = 'vi-VN-HoaiMyNeural'
    rate = '+0%'
    print(f'📂 [DEBUG] Thư mục hiện tại: {os.getcwd()}')
    print(f"📁 [DEBUG] Thư mục static hiện có: {os.path.exists('static')}")
    try:
        print(f'🔄 [DEBUG] Cấu hình provider: {provider_type}')
        pipeline.tts_service.provider_type = provider_type
        pipeline.tts_service.provider = None
        print('⏳ [DEBUG] Đang gọi pipeline.tts_speak...')
        output_path = await pipeline.tts_speak(text, 'vi', voice=voice, rate=rate)
        if output_path:
            print(f'✅ [DEBUG] Kết quả output_path: {output_path}')
            if os.path.exists(output_path):
                print(f'✅ [DEBUG] File thực sự tồn tại: {output_path} ({os.path.getsize(output_path)} bytes)')
            else:
                print(f'❌ [DEBUG] File KHÔNG tồn tại tại đường dẫn: {output_path}')
        else:
            print('❌ [DEBUG] tts_speak trả về None')
    except Exception as e:
        print(f'💥 [DEBUG] Lỗi phát sinh trong quá trình xử lý: {e}')
        import traceback
        traceback.print_exc()
if __name__ == '__main__':
    asyncio.run(debug_tts_flow())