from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import uuid
import asyncio
import logging
from datetime import datetime
import uvicorn
import os
import json
import threading
from contextlib import asynccontextmanager
import concurrent.futures
from audio_processor import AudioProcessor
from config import DEEPGRAM_API_KEYS, GOOGLE_API_KEYS, MAX_WORDS, DEEPGRAM_MODEL, GOOGLE_AI_MODEL, TELEGRAM_BOT_ENABLED, TELEGRAM_ADMIN_CHAT_ID, AUDIO_PROCESSING_MODE, DEBUG_MODE, MIN_DURATION_THRESHOLD, ENGINE, MAX_WORKER_PROCESSES, AUTO_RESUME_QUEUE
from telegram_bot import TelegramBot
from telegram_handler import TelegramHandler
from queue_manager import QueueManager
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
db_manager = None
telegram_bot = None
telegram_handler = None
queue_manager = None
pipeline_service = None
main_loop = None
process_executor = None
from src.core.task_store import task_store

@asynccontextmanager
async def lifespan(app: FastAPI):
    global telegram_bot, telegram_handler, queue_manager, pipeline_service
    'Lifespan handler cho FastAPI'
    global main_loop
    main_loop = asyncio.get_running_loop()
    logger.info('Khởi tạo STT-Nova2 Service...')
    global process_executor
    process_executor = concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKER_PROCESSES)
    logger.info(f'🚀 Initialized Process Pool with {MAX_WORKER_PROCESSES} workers')
    from src.chatbot.ai_hub_service import ai_hub_service
    ai_hub_service.set_executor(process_executor)
    from src.chatbot.file_processor import file_processor
    file_processor.set_executor(process_executor)
    logger.info('📦 Pre-loading models...')
    try:
        from preload_models import preload_models
        preload_models()
        logger.info('✅ Models pre-loaded successfully')
    except Exception as e:
        logger.error(f'❌ Failed to pre-load models: {e}')
    await init_telegram_bot()
    from src.chatbot.router import set_telegram_bot
    if telegram_bot:
        set_telegram_bot(telegram_bot)
    await init_telegram_handler()
    if telegram_bot and TELEGRAM_BOT_ENABLED:
        try:
            await telegram_bot.notify_service_startup()
            logger.info('Đã gửi thông báo startup qua Telegram')
        except Exception as e:
            logger.error(f'Lỗi gửi thông báo startup Telegram: {e}')
    init_queue_manager()
    await init_pipeline_service()
    try:
        from database import DatabaseManager
        global db_manager
        db_manager = DatabaseManager()
        await db_manager.initialize()
        logger.info('Database manager đã được khởi tạo thành công')
    except Exception as e:
        logger.error(f'Lỗi khi khởi tạo Database manager: {e}')
    if queue_manager and AUTO_RESUME_QUEUE:
        queue_manager.resume_processing(process_single_url)
    elif queue_manager and (not AUTO_RESUME_QUEUE):
        logger.info('Auto-resume bị tắt, không tự động xử lý queue')
    logger.info('STT-Nova2 Service đã sẵn sàng!')
    yield
    logger.info('Đang dừng STT-Nova2 Service...')
    if process_executor:
        logger.info('⏳ Đang dừng Process Pool (cancelling pending tasks)...')
        process_executor.shutdown(wait=True, cancel_futures=True)
        logger.info('✅ Đã dừng Process Pool')
    if telegram_handler:
        try:
            telegram_handler.stop()
            logger.info('Đã dừng Telegram handler')
        except Exception as e:
            logger.error(f'Lỗi khi dừng Telegram handler: {e}')
    if queue_manager:
        try:
            queue_manager.stop_processing()
            logger.info('Đã dừng Queue manager')
        except Exception as e:
            logger.error(f'Lỗi khi dừng Queue manager: {e}')
    try:
        await db_manager.close()
        logger.info('Đã đóng Database connections')
    except Exception as e:
        logger.error(f'Lỗi khi đóng Database connections: {e}')
    logger.info('STT-Nova2 Service đã dừng thành công!')
app = FastAPI(title='STT-Nova2 Professional API & AI Hub', description='Advanced STT, TTS (VieNeu-TTS) and Stateless AI Hub Central (OCR, STT, Vectorization)', version='2.2.0', lifespan=lifespan)

@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse('static/favicon.png')
app.mount('/static', StaticFiles(directory='static'), name='static')

class ProcessRequest(BaseModel):
    urls: List[str] = Field(..., description='Danh sách URLs của các file audio cần xử lý', json_schema_extra={'example': ['https://pbx.example.com/recording1.wav', 'https://pbx.example.com/recording2.wav']})
    audio_processing_mode: Optional[str] = Field(default=None, description='Chế độ tiền xử lý audio:\n- `auto`: Tự động phát hiện và xử lý (mặc định)\n- `off`: Không tiền xử lý, gửi thẳng audio gốc\n- `enhance_all`: Giảm nhiễu + tăng giọng nói\n- `enhance_speech`: Chỉ tăng cường giọng nói\n- `normal`: Giảm nhiễu nhẹ\n- `aggressive`: Giảm nhiễu mạnh\n- `conservative`: Giảm nhiễu nhẹ nhàng', json_schema_extra={'example': 'enhance_all'})
    max_words: Optional[int] = Field(default=MAX_WORDS, description='Số từ tối đa cho bản tóm tắt (summary)', json_schema_extra={'example': 150})
    use_queue: Optional[bool] = Field(default=True, description='Sử dụng hàng đợi để xử lý tuần tự (khuyến nghị cho nhiều URLs)', json_schema_extra={'example': True})
    engine: Optional[str] = Field(default=None, description="Engine STT: 'deepgram' (cloud, nhanh) hoặc 'phowhisper' (local, miễn phí)", json_schema_extra={'example': 'deepgram'})
    billsec: Optional[int] = Field(default=0, description='Thời lượng thực tế cuộc gọi (giây) - dùng để trim audio', json_schema_extra={'example': 37})
    duration: Optional[int] = Field(default=0, description='Tổng thời lượng file audio (giây)', json_schema_extra={'example': 45})
    callback_url: Optional[str] = Field(default=None, description='URL webhook để nhận kết quả sau khi xử lý xong (async mode)', json_schema_extra={'example': 'https://your-server.com/api/stt-callback'})

class TTSRequest(BaseModel):
    text: str = Field(..., description='Văn bản cần chuyển thành giọng nói', json_schema_extra={'example': 'Xin chào, đây là bản tin thời tiết hôm nay.'})
    language: Optional[str] = Field(default='vi', description='Mã ngôn ngữ (vi, en, ...)', json_schema_extra={'example': 'vi'})
    voice: Optional[str] = Field(default=None, description="Giọng đọc:\n- Edge TTS: 'vi-VN-HoaiMyNeural' (Nữ Bắc), 'vi-VN-NamMinhNeural' (Nam Bắc)\n- VieNeu: 'Nguyên', 'Tuyên', 'Sơn', 'Đoan', 'Dung', 'Ly', 'Ngọc', 'Hương', 'Bình', 'Vĩnh'", json_schema_extra={'example': 'vi-VN-HoaiMyNeural'})
    rate: Optional[str] = Field(default='+0%', description="Tốc độ đọc: từ '-50%' (chậm) đến '+50%' (nhanh)", json_schema_extra={'example': '+10%'})
    provider: Optional[str] = Field(default='edge', description="Provider TTS: 'edge' (Microsoft Edge, miễn phí) hoặc 'vieneu' (VieNeu-TTS, chất lượng cao)", json_schema_extra={'example': 'edge'})
    return_json: bool = Field(default=False, description='Trả về JSON với audio_url thay vì file audio trực tiếp', json_schema_extra={'example': False})

class WebhookRequest(BaseModel):
    recording_url: str = Field(..., description='URL của file audio cần xử lý (bắt buộc)', json_schema_extra={'example': 'https://conek-pbx.conek.vn/app/xml_cdr/download.php?id=9acc2e32-5b32-4617-abde-180719eaf9c9'})
    xml_cdr_uuid: str = Field(..., description='UUID duy nhất của bản ghi CDR (bắt buộc)', json_schema_extra={'example': '9acc2e32-5b32-4617-abde-180719eaf9c9'})
    direction: Optional[str] = Field(default='', description="Hướng cuộc gọi: 'inbound' hoặc 'outbound'. Chỉ xử lý direction='outbound'", json_schema_extra={'example': 'outbound'})
    billsec: Optional[int] = Field(default=0, description='Thời lượng thực tế cuộc gọi (giây). Yêu cầu > 10s để xử lý', json_schema_extra={'example': 37})
    duration: Optional[int] = Field(default=0, description='Tổng thời lượng file audio (giây)', json_schema_extra={'example': 45})
    callback_url: Optional[str] = Field(default=None, description='URL webhook để nhận kết quả sau khi xử lý xong. Nếu không truyền, dùng GET /v1/tasks/{task_id} để poll kết quả', json_schema_extra={'example': 'https://your-server.com/webhook/stt-result'})

class QueueStatusResponse(BaseModel):
    queue_length: int = Field(..., description='Số lượng URLs đang chờ trong hàng đợi')
    is_processing: bool = Field(..., description='Đang xử lý hay không')
    total_processed: int = Field(..., description='Tổng số đã xử lý thành công')
    total_failed: int = Field(..., description='Tổng số xử lý thất bại')
    current_batch: int = Field(..., description='Batch hiện tại đang xử lý')
    last_processed_time: Optional[str] = Field(None, description='Thời gian xử lý gần nhất')
    batch_size: int = Field(..., description='Số URLs mỗi batch')
    max_workers: int = Field(..., description='Số worker tối đa')

async def init_telegram_bot():
    global telegram_bot
    if TELEGRAM_BOT_ENABLED:
        try:
            telegram_bot = TelegramBot()
            await telegram_bot.__aenter__()
            logger.info('Telegram bot đã được khởi tạo thành công')
        except Exception as e:
            logger.error(f'Lỗi khi khởi tạo Telegram bot: {e}')

async def init_telegram_handler():
    global telegram_handler
    if TELEGRAM_BOT_ENABLED:
        try:
            telegram_handler = TelegramHandler()
            await telegram_handler.__aenter__()
            await asyncio.sleep(0.1)
            task = asyncio.create_task(telegram_handler.process_updates())
            telegram_handler._polling_task = task
            logger.info('Telegram handler initialized and started polling')
        except Exception as e:
            logger.error(f'Lỗi khi khởi tạo Telegram handler: {e}')

def init_queue_manager():
    global queue_manager
    try:
        queue_manager = QueueManager(telegram_bot)
        logger.info('Queue manager đã được khởi tạo thành công')
    except Exception as e:
        logger.error(f'Lỗi khi khởi tạo Queue manager: {e}')

async def init_pipeline_service():
    global pipeline_service
    try:
        from src.services.pipeline_service import PipelineService
        pipeline_service = PipelineService()
        await pipeline_service.initialize()
        try:
            from src.chatbot.file_processor import file_processor
            file_processor.transcriber = pipeline_service.transcriber
            logger.info('✅ Transcriber linked to FileProcessor for AI Hub')
        except Exception as fe:
            logger.warning(f'⚠️ Could not link transcriber to FileProcessor: {fe}')
        logger.info('Pipeline Service đã được khởi tạo thành công')
    except Exception as e:
        logger.error(f'Lỗi khi khởi tạo Pipeline Service: {e}')

async def send_webhook_callback(callback_url: str, task_id: str, result: Dict[str, Any]):
    try:
        import aiohttp
        payload = {'task_id': task_id, 'status': 'completed' if result.get('success') else 'failed', 'result': result, 'timestamp': datetime.now().isoformat()}
        async with aiohttp.ClientSession() as session:
            async with session.post(callback_url, json=payload, timeout=10) as response:
                if response.status == 200:
                    logger.info(f'✅ Webhook callback sent successfully to {callback_url}')
                else:
                    logger.warning(f'⚠️ Webhook callback failed with status {response.status} for {callback_url}')
    except Exception as e:
        logger.error(f'❌ Error sending webhook callback: {e}')

def process_single_url(url: str, audio_processing_mode: str=None, trim_info: Dict[str, Any]=None, task_id: str=None, callback_url: str=None) -> Dict[str, Any]:
    if task_id:
        task_store.update_task(task_id, 'processing')
    try:
        if not pipeline_service:
            return {'url': url, 'success': False, 'error': 'Pipeline Service chưa được khởi tạo'}
        options = {}
        if audio_processing_mode:
            options['audio_processing_mode'] = audio_processing_mode
        if main_loop:
            future = asyncio.run_coroutine_threadsafe(pipeline_service.process_request([url], options), main_loop)
            results = future.result()
        else:
            results = asyncio.run(pipeline_service.process_request([url], options))
        if not results:
            return {'url': url, 'success': False, 'error': 'No result returned'}
        result = results[0]
        status = result.get('status', 'failed')
        success = status == 'completed'
        final_result = {'url': url, 'success': success, 'transcript': result.get('transcript', ''), 'summary': result.get('summary', ''), 'call_topic': result.get('call_topic', 'N/A'), 'transcript_length': len(result.get('transcript', '')), 'summary_length': len(result.get('summary', '')), 'error': result.get('error', '') if not success else None}
        if task_id:
            task_store.update_task(task_id, 'completed' if success else 'failed', final_result)
        if callback_url and main_loop:
            asyncio.run_coroutine_threadsafe(send_webhook_callback(callback_url, task_id, final_result), main_loop)
        return final_result
    except Exception as e:
        logger.error(f'Lỗi khi xử lý URL {url}: {e}')
        if task_id:
            task_store.update_task(task_id, 'failed', {'error': str(e)})
        return {'url': url, 'success': False, 'error': str(e)}

@app.get('/v1/tasks/{task_id}')
async def get_task_status(task_id: str):
    task = task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task không tồn tại')
    return task

@app.get('/')
async def root():
    return FileResponse('static/index.html')

@app.get('/v1/tts/voices')
async def get_voices():
    voices = {'edge': [{'id': 'vi-VN-HoaiMyNeural', 'name': 'Hoài My (Nữ - Bắc)'}, {'id': 'vi-VN-NamMinhNeural', 'name': 'Nam Minh (Nam - Bắc)'}], 'vieneu': []}
    if pipeline_service and pipeline_service.tts_service:
        provider = pipeline_service.tts_service._get_provider('vieneu')
        if hasattr(provider, 'voices'):
            for v_name in provider.voices.keys():
                voices['vieneu'].append({'id': v_name, 'name': v_name})
    return voices

@app.post('/v1/docs/parse')
async def parse_document(file: UploadFile=File(...)):
    if not pipeline_service or not pipeline_service.doc_connector:
        raise HTTPException(status_code=503, detail='Document processor not initialized')
    try:
        import uuid
        import os
        os.makedirs('temp', exist_ok=True)
        ext = os.path.splitext(file.filename)[1]
        temp_path = f'temp/doc_{uuid.uuid4()}{ext}'
        with open(temp_path, 'wb') as f:
            f.write(await file.read())
        context = {'document_path': temp_path, 'status': 'processing'}
        context = await pipeline_service.doc_connector.process(context)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if 'transcript' in context:
            return {'text': context['transcript']}
        else:
            raise HTTPException(status_code=500, detail='Không thể trích xuất văn bản từ file này')
    except Exception as e:
        logger.error(f'Doc parse error: {e}')
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/health')
async def health_check():
    return {'service': 'STT-Nova2', 'status': 'running', 'version': '1.0.0', 'endpoints': {'health': '/health', 'process': '/process', 'webhook': '/webhook', 'queue_status': '/queue/status', 'queue_start': '/queue/start', 'queue_stop': '/queue/stop', 'docs': '/docs'}}

@app.post('/process')
async def process_audio(request: ProcessRequest):
    try:
        if not request.urls:
            raise HTTPException(status_code=400, detail='URLs không được để trống')
        if len(request.urls) > 100:
            raise HTTPException(status_code=400, detail='Tối đa 100 URLs mỗi request')
        request_id = str(uuid.uuid4())
        if request.use_queue and len(request.urls) > 1:
            if not queue_manager:
                raise HTTPException(status_code=500, detail='Queue manager chưa sẵn sàng')
            queue_result = queue_manager.add_urls(request.urls, request.audio_processing_mode)
            if not queue_result['success']:
                raise HTTPException(status_code=500, detail=queue_result['message'])
            if not queue_manager.processing:
                queue_manager.start_processing(process_single_url)
            return {'request_id': request_id, 'status': 'queued', 'message': f'Đã thêm {len(request.urls)} URLs vào queue', 'queue_info': {'total_in_queue': queue_result['total_in_queue'], 'batch_size': queue_manager.get_queue_status()['batch_size'], 'estimated_batches': (queue_result['total_in_queue'] + len(request.urls) - 1) // queue_manager.get_queue_status()['batch_size']}, 'results': None, 'error': None}
        else:
            if not audio_processor:
                raise HTTPException(status_code=500, detail='Audio processor chưa sẵn sàng')
            audio_processor.audio_processing_mode = request.audio_processing_mode
            audio_processor.max_words = request.max_words
            if request.engine in ('deepgram', 'phowhisper'):
                try:
                    audio_processor.engine = request.engine
                except Exception:
                    pass
            results = []
            for i, url in enumerate(request.urls):
                try:
                    logger.info(f'Xử lý URL {i + 1}/{len(request.urls)}: {url}')
                    result = await audio_processor.process_audio(url, trim_info={'duration': request.duration, 'billsec': request.billsec})
                    results.append({'url': url, 'index': i, 'success': result['success'], 'transcript': result.get('transcript', ''), 'summary': result.get('summary', ''), 'call_topic': result.get('call_topic', 'N/A'), 'transcript_length': len(result.get('transcript', '')), 'summary_length': len(result.get('summary', '')), 'error': result.get('message', '') if not result['success'] else None})
                    try:
                        from stats_manager import stats_manager
                        if result['success']:
                            stats_manager.increment_processed(1)
                        else:
                            stats_manager.increment_failed(1)
                    except Exception as e:
                        logger.warning(f'Không thể cập nhật global stats: {e}')
                except Exception as e:
                    logger.error(f'Lỗi khi xử lý URL {url}: {e}')
                    results.append({'url': url, 'index': i, 'success': False, 'transcript': None, 'summary': None, 'call_topic': 'N/A', 'error': str(e)})
                    try:
                        from stats_manager import stats_manager
                        stats_manager.increment_failed(1)
                    except Exception as e:
                        logger.warning(f'Không thể cập nhật global stats: {e}')
            return {'request_id': request_id, 'status': 'completed', 'message': f'Hoàn thành xử lý {len(request.urls)} URLs', 'results': results, 'error': None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Lỗi khi xử lý request: {e}')
        raise HTTPException(status_code=500, detail=f'Lỗi server: {str(e)}')

@app.post('/webhook')
async def webhook_handler(request: WebhookRequest):
    try:
        if not request.recording_url:
            raise HTTPException(status_code=400, detail='recording_url không được để trống')
        if not request.xml_cdr_uuid:
            raise HTTPException(status_code=400, detail='xml_cdr_uuid không được để trống')
        request_id = str(uuid.uuid4())
        logger.info(f'Webhook nhận được: xml_cdr_uuid={request.xml_cdr_uuid}, direction={request.direction}, billsec={request.billsec}s, duration={request.duration}s')
        should_process = False
        skip_reason = ''
        if request.direction != 'outbound':
            skip_reason = f'Direction không phải outbound: {request.direction}'
        elif request.billsec <= MIN_DURATION_THRESHOLD:
            skip_reason = f'Billsec quá ngắn: {request.billsec}s (cần >{MIN_DURATION_THRESHOLD}s)'
        else:
            should_process = True
        if not should_process:
            logger.info(f'Bỏ qua xử lý: {skip_reason}')
            response = {'request_id': request_id, 'xml_cdr_uuid': request.xml_cdr_uuid, 'status': 'skipped', 'recording_url': request.recording_url, 'direction': request.direction, 'billsec': request.billsec, 'skip_reason': skip_reason, 'transcript': '', 'summary': '', 'call_topic': 'N/A', 'transcript_length': 0, 'summary_length': 0, 'error': None, 'processing_time': 0, 'timestamp': datetime.now().isoformat()}
            if request.xml_cdr_uuid:
                try:
                    if db_manager is None:
                        logger.error('db_manager is None in webhook handler')
                    else:
                        db_success = await db_manager.update_cdr_transcript(cdr_uuid=request.xml_cdr_uuid, transcript='', summary=f'SKIPPED: {skip_reason}', call_topic='N/A')
                        if db_success:
                            logger.info(f'Successfully recorded skipped CDR: {request.xml_cdr_uuid} - {skip_reason}')
                        else:
                            logger.warning(f'FAILED - CDR skip record failed: {request.xml_cdr_uuid}')
                except Exception as e:
                    logger.error(f'ERROR - CDR skip record error: {e}')
            return response
        if queue_manager:
            queue_status = queue_manager.get_queue_status()
            if queue_status.get('is_processing', False):
                current_processing_url = queue_manager._get_current_processing_url()
                if current_processing_url == request.recording_url:
                    if DEBUG_MODE:
                        logger.info(f'Duplicate URL đang được xử lý: {request.recording_url} - Returning 200 to stop retries')
                    return {'request_id': request_id, 'xml_cdr_uuid': request.xml_cdr_uuid, 'status': 'already_processing', 'recording_url': request.recording_url, 'message': 'Request is being processed, ignoring duplicate'}
            queue_urls = queue_manager._read_urls()
            if request.recording_url in queue_urls:
                if DEBUG_MODE:
                    logger.info(f'Duplicate URL trong queue: {request.recording_url} - Returning 200 to stop retries')
                return {'request_id': request_id, 'xml_cdr_uuid': request.xml_cdr_uuid, 'status': 'already_queued', 'recording_url': request.recording_url, 'message': 'Request already in queue, ignoring duplicate'}
        if queue_manager:
            queue_result = queue_manager.add_urls([request.recording_url], AUDIO_PROCESSING_MODE, options={'task_id': request_id, 'callback_url': request.callback_url})
            if not queue_result['success']:
                raise HTTPException(status_code=500, detail=queue_result['message'])
            task_store.create_task(request_id, {'xml_cdr_uuid': request.xml_cdr_uuid, 'recording_url': request.recording_url, 'direction': request.direction})
            if not queue_manager.processing:
                queue_manager.start_processing(process_single_url)
            return {'task_id': request_id, 'xml_cdr_uuid': request.xml_cdr_uuid, 'status': 'queued', 'recording_url': request.recording_url, 'message': 'Request received and queued for processing'}
        else:
            if not audio_processor:
                raise HTTPException(status_code=500, detail='Audio processor chưa sẵn sàng')
            audio_processor.audio_processing_mode = AUDIO_PROCESSING_MODE
            audio_processor.max_words = MAX_WORDS
            if DEBUG_MODE:
                logger.info(f'🚀 Bắt đầu xử lý audio với mode: {AUDIO_PROCESSING_MODE}, max_words: {MAX_WORDS}')
            result = await audio_processor.process_audio(request.recording_url, trim_info={'duration': request.duration, 'billsec': request.billsec})
            response = {'request_id': request_id, 'xml_cdr_uuid': request.xml_cdr_uuid, 'status': 'completed' if result['success'] else 'failed', 'recording_url': request.recording_url, 'direction': request.direction, 'billsec': request.billsec, 'transcript': result.get('transcript', ''), 'summary': result.get('summary', ''), 'call_topic': result.get('call_topic', 'N/A'), 'transcript_length': len(result.get('transcript', '')), 'summary_length': len(result.get('summary', '')), 'error': result.get('message', '') if not result['success'] else None, 'processing_time': result.get('processing_time', 0), 'timestamp': datetime.now().isoformat()}
        if result['success'] and request.xml_cdr_uuid:
            try:
                if db_manager is None:
                    pass
                else:
                    db_success = await db_manager.update_cdr_transcript(cdr_uuid=request.xml_cdr_uuid, transcript=result.get('transcript', ''), summary=result.get('summary', ''), call_topic=result.get('call_topic', 'N/A'))
                    if db_success:
                        logger.info(f'Successfully updated CDR record: {request.xml_cdr_uuid}')
                        try:
                            from stats_manager import stats_manager
                            stats_manager.increment_processed(1)
                        except Exception as e:
                            logger.warning(f'Không thể cập nhật global stats: {e}')
                    else:
                        logger.warning(f'FAILED - CDR update failed: {request.xml_cdr_uuid}')
                        try:
                            from stats_manager import stats_manager
                            stats_manager.increment_failed(1)
                        except Exception as e:
                            logger.warning(f'Không thể cập nhật global stats: {e}')
            except Exception as e:
                logger.error(f'ERROR - CDR update error: {e}')
                try:
                    from stats_manager import stats_manager
                    stats_manager.increment_failed(1)
                except Exception as e:
                    logger.warning(f'Không thể cập nhật global stats: {e}')
        elif not result['success']:
            error_message = result.get('message', 'Unknown processing error')
            logger.error(f'Processing failed: {request.xml_cdr_uuid} - {error_message}')
            if telegram_bot:
                try:
                    await telegram_bot.notify_processing_error(error_message=error_message, url=request.recording_url, xml_cdr_uuid=request.xml_cdr_uuid)
                except Exception as e:
                    logger.error(f'Không thể gửi thông báo lỗi qua Telegram: {e}')
            if request.xml_cdr_uuid:
                try:
                    if db_manager is None:
                        logger.error('db_manager is None in webhook handler')
                    else:
                        db_success = await db_manager.update_cdr_transcript(cdr_uuid=request.xml_cdr_uuid, transcript='', summary=f'FAILED: {error_message}', call_topic='N/A')
                        if db_success:
                            logger.info(f'Successfully recorded failed CDR: {request.xml_cdr_uuid} - {error_message}')
                        else:
                            logger.warning(f'FAILED - CDR failure record failed: {request.xml_cdr_uuid}')
                except Exception as e:
                    logger.error(f'ERROR - CDR failure record error: {e}')
            try:
                from stats_manager import stats_manager
                stats_manager.increment_failed(1)
            except Exception as e:
                logger.warning(f'Không thể cập nhật global stats: {e}')
        elif not request.xml_cdr_uuid:
            if DEBUG_MODE:
                logger.info('SKIP - Missing xml_cdr_uuid')
        if DEBUG_MODE:
            logger.info(f"Webhook xử lý hoàn thành: xml_cdr_uuid={request.xml_cdr_uuid}, status={response['status']}")
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Lỗi khi xử lý webhook: {e}')
        raise HTTPException(status_code=500, detail=f'Lỗi server: {str(e)}')

@app.post('/v1/tts/speak')
async def tts_speak(request: TTSRequest):
    if not pipeline_service:
        logger.error('Pipeline Service not initialized')
        raise HTTPException(status_code=500, detail='Pipeline Service not initialized')
    try:
        logger.info(f'🎙️ TTS Request: provider={request.provider}, voice={request.voice}, rate={request.rate}')
        p_type = request.provider or pipeline_service.tts_service.provider_type
        output_path = await pipeline_service.tts_speak(request.text, request.language, voice=request.voice, rate=request.rate, provider=p_type)
        if not output_path or not os.path.exists(output_path):
            logger.error(f'TTS generation failed or file not found: {output_path}')
            raise HTTPException(status_code=500, detail='TTS generation failed')
        audio_url = f'/static/{os.path.basename(output_path)}'
        if request.return_json:
            return {'status': 'success', 'audio_url': audio_url, 'text': request.text, 'provider': p_type, 'voice': request.voice}
        return FileResponse(output_path, media_type='audio/wav', filename='tts_output.wav')
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'❌ TTS Endpoint Error: {e}')
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/v1/tts/clone')
async def tts_clone(text: str=Form(...), reference_file: UploadFile=File(None), voice: Optional[str]=Form(None), rate: str=Form('+0%'), return_json: bool=Form(False)):
    if not pipeline_service:
        raise HTTPException(status_code=500, detail='Pipeline Service not initialized')
    temp_input_path = None
    temp_wav_path = None
    try:
        audio_path = None
        if reference_file and reference_file.filename:
            original_ext = os.path.splitext(reference_file.filename)[1] or '.wav'
            temp_input_path = f'temp_ref_in_{uuid.uuid4()}{original_ext}'
            temp_wav_path = f'temp_ref_out_{uuid.uuid4()}.wav'
            with open(temp_input_path, 'wb') as buffer:
                content = await reference_file.read()
                buffer.write(content)
            import subprocess
            try:
                command = ['ffmpeg', '-i', temp_input_path, '-ac', '1', '-ar', '22050', '-y', temp_wav_path]
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                audio_path = await pipeline_service.voice_clone(text, temp_wav_path, rate=rate)
            except Exception as fe:
                logger.warning(f'FFmpeg conversion failed: {fe}. Attempting to use original file.')
                audio_path = await pipeline_service.voice_clone(text, temp_input_path, rate=rate)
        elif voice:
            audio_path = await pipeline_service.tts_speak(text, provider='vieneu', voice=voice, rate=rate)
        else:
            raise HTTPException(status_code=400, detail='Cần cung cấp file mẫu hoặc chọn giọng mẫu có sẵn')
        if not audio_path or not os.path.exists(audio_path):
            raise HTTPException(status_code=500, detail='Nhân bản giọng nói thất bại')
        audio_url = f'/static/{os.path.basename(audio_path)}'
        if return_json:
            return {'status': 'success', 'audio_url': audio_url, 'text': text}
        return FileResponse(audio_path, media_type='audio/wav', filename='cloned_output.wav')
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f'❌ Clone Endpoint Error: {e}')
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for p in [temp_input_path, temp_wav_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass

@app.post('/v1/process')
async def unified_process(request: ProcessRequest):
    return await process_audio(request)

@app.get('/queue/status')
async def get_queue_status():
    if not queue_manager:
        raise HTTPException(status_code=500, detail='Queue manager chưa sẵn sàng')
    status = queue_manager.get_queue_status()
    return QueueStatusResponse(**status)

@app.post('/queue/start')
async def start_queue_processing():
    if not queue_manager:
        raise HTTPException(status_code=500, detail='Queue manager chưa sẵn sàng')
    if queue_manager.processing:
        return {'message': 'Queue đang được xử lý'}
    success = queue_manager.start_processing(process_single_url)
    if success:
        return {'message': 'Đã bắt đầu xử lý queue'}
    else:
        raise HTTPException(status_code=500, detail='Không thể bắt đầu xử lý queue')

@app.post('/queue/stop')
async def stop_queue_processing():
    if not queue_manager:
        raise HTTPException(status_code=500, detail='Queue manager chưa sẵn sàng')
    queue_manager.stop_processing()
    return {'message': 'Đã dừng xử lý queue'}

@app.get('/queue/clear')
async def clear_queue():
    if not queue_manager:
        raise HTTPException(status_code=500, detail='Queue manager chưa sẵn sàng')
    queue_manager.stop_processing()
    if os.path.exists('queue_data/queue.json'):
        with open('queue_data/queue.json', 'w', encoding='utf-8') as f:
            json.dump([], f)
    return {'message': 'Đã dừng processing và xóa queue'}

@app.get('/queue/dead-letter')
async def get_dead_letter_queue():
    if not queue_manager:
        raise HTTPException(status_code=500, detail='Queue manager chưa sẵn sàng')
    return {'dead_letter_queue': queue_manager.get_dead_letter_queue(), 'count': len(queue_manager.get_dead_letter_queue())}

@app.post('/queue/dead-letter/{item_id}/retry')
async def retry_dead_letter_item(item_id: str):
    if not queue_manager:
        raise HTTPException(status_code=500, detail='Queue manager chưa sẵn sàng')
    success = queue_manager.retry_dead_letter_item(item_id)
    if success:
        return {'message': f'Đã đưa item {item_id} trở lại queue để xử lý'}
    else:
        raise HTTPException(status_code=404, detail=f'Không tìm thấy item {item_id} trong dead letter queue')

@app.delete('/queue/dead-letter/{item_id}')
async def delete_dead_letter_item(item_id: str):
    if not queue_manager:
        raise HTTPException(status_code=500, detail='Queue manager chưa sẵn sàng')
    success = queue_manager.clear_dead_letter_item(item_id)
    if success:
        return {'message': f'Đã xóa item {item_id} khỏi dead letter queue'}
    else:
        raise HTTPException(status_code=404, detail=f'Không tìm thấy item {item_id} trong dead letter queue')

@app.get('/v1/tasks/{task_id}')
async def get_task_status(task_id: str):
    task = task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task không tồn tại')
    return task

@app.post('/service/restart')
async def restart_service_components():
    try:
        global telegram_bot, telegram_handler, queue_manager, pipeline_service
        restart_log = []
        restart_log.append('🔄 Bắt đầu restart service components...')
        telegram_bot = None
        telegram_handler = None
        queue_manager = None
        pipeline_service = None
        restart_log.append('✅ Reset global variables')
        await init_telegram_bot()
        restart_log.append('✅ Telegram bot đã được khởi tạo lại')
        restart_log.append('⏳ Chờ Telegram handler gửi thông báo restart')
        init_queue_manager()
        restart_log.append('✅ Queue manager đã được khởi tạo lại')
        await init_pipeline_service()
        restart_log.append('✅ Pipeline Service đã được khởi tạo lại')
        return {'status': 'success', 'message': 'Service components restart thành công', 'restart_log': restart_log, 'components_status': {'telegram_bot': telegram_bot is not None, 'telegram_handler': telegram_handler is not None, 'queue_manager': queue_manager is not None, 'pipeline_service': pipeline_service is not None}, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    except Exception as e:
        logger.error(f'Error in restart_service_components: {e}')
        return {'status': 'error', 'message': f'Failed to restart service components: {str(e)}', 'restart_log': [f'❌ Critical error: {str(e)}'], 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
from src.chatbot.router import chatbot_router
app.include_router(chatbot_router, prefix='/v1')
if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)