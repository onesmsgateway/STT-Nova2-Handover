import asyncio
import sys
import os
sys.path.append(os.getcwd())
from src.services.pipeline_service import PipelineService
from src.core.logger import setup_logger
logger = setup_logger(__name__)

async def main():
    print('🚀 Starting Manual Doc & TTS Test...')
    pipeline = PipelineService()
    await pipeline.initialize()
    dummy_wav_path = 'resource/dummy_ref.wav'
    if not os.path.exists(dummy_wav_path):
        import wave
        import struct
        with wave.open(dummy_wav_path, 'w') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(22050)
            f.writeframes(b'\x00' * 22050 * 2)
        print(f'Created dummy reference audio at {dummy_wav_path}')
    print('\n[1] Testing TTS...')
    text_to_speak = 'Chào bạn, đây là thử nghiệm giọng nói Tiếng Việt với mô hình viXTTS.'
    output_audio_path = 'tests/tts_output.wav'
    vi_sample = '/app/resource/models/vixtts/vi_sample.wav'
    if os.path.exists(vi_sample):
        print(f' > Using valid vi_sample.wav for XTTS: {vi_sample}')
        reference_path = vi_sample
    else:
        reference_path = dummy_wav_path
    success = await pipeline.generate_speech(text=text_to_speak, output_path=output_audio_path, speaker_wav=reference_path, language='vi')
    reference_audio_path = None
    if success and os.path.exists(output_audio_path):
        print(f'✅ TTS Success! Audio saved to: {output_audio_path}')
        reference_audio_path = output_audio_path
    else:
        print('❌ TTS Failed')
    if reference_audio_path:
        print('\n[2] Testing Voice Cloning (using TTS output as reference)...')
        cloned_output_path = 'tests/voice_clone_output.wav'
        clone_text = 'Đây là giọng nhái tiếng Việt được tạo ra từ file mẫu.'
        clone_success = await pipeline.clone_voice(reference_path=reference_audio_path, text=clone_text, output_path=cloned_output_path)
        if clone_success and os.path.exists(cloned_output_path):
            print(f'✅ Voice Cloning Success! Audio saved to: {cloned_output_path}')
        else:
            print('❌ Voice Cloning Failed')
    else:
        print('\n[2] Skipping Voice Clone (No reference audio from TTS step)')
    print('\n[3] Testing Document Processing...')
    dummy_pdf_path = 'tests/dummy_test.pdf'
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(dummy_pdf_path)
        c.drawString(100, 750, 'Day la file PDF thu nghiem cho Document Processor.')
        c.save()
        print(f'Created dummy PDF at {dummy_pdf_path}')
    except ImportError:
        print('reportlab not installed, skipping PDF generation. Using manual checking if file exists.')
        try:
            from PyPDF2 import PdfWriter, PdfReader
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=200)
            with open(dummy_pdf_path, 'wb') as f:
                writer.write(f)
            print(f'Created dummy blank PDF using PyPDF2 at {dummy_pdf_path}')
        except Exception as e:
            print(f'Could not create dummy PDF: {e}')
            dummy_pdf_path = None
    doc_paths = sys.argv[1:]
    if not doc_paths and dummy_pdf_path and os.path.exists(dummy_pdf_path):
        doc_paths = [dummy_pdf_path]
    if doc_paths:
        for doc_path in doc_paths:
            print(f'Processing: {doc_path}')
            results = await pipeline.process_request([doc_path])
            if results and results[0].get('status') == 'completed':
                print('✅ Doc Processing Success!')
                print('Summary Preview:', results[0].get('summary', '')[:100])
                print('Extracted Text Preview:', results[0].get('transcript', '')[:100])
            else:
                error_msg = results[0].get('error') if results else 'Unknown error'
                print(f'❌ Failed to process {doc_path}. Error: {error_msg}')
    else:
        print('No document provided and failed to generate dummy PDF.')
    await pipeline.notifier.stop()
if __name__ == '__main__':
    asyncio.run(main())