from fastapi import APIRouter, HTTPException, Body, UploadFile, File, Form
from pydantic import BaseModel
import logging
from typing import Dict, Any, List, Optional
from .llm_client import gemini_client
from .prompt_manager import prompt_manager
from .file_processor import file_processor
from .vector_store import vector_store
from .ai_hub_service import ai_hub_service
from src.core.task_store import task_store
from src.core.task_store import task_store
import json
import asyncio
chatbot_router = APIRouter(tags=['Chatbot / AI Hub'])
logger = logging.getLogger(__name__)
telegram_bot = None

def set_telegram_bot(bot_instance):
    global telegram_bot
    telegram_bot = bot_instance
    logger.info('✅ Telegram Bot injected into Chatbot Router')

class ChatRequest(BaseModel):
    message: str
    context_type: str = 'general'
    school_code: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = []
    tools: Optional[List[Dict[str, Any]]] = None
    service_name: Optional[str] = 'unknown_service'
    ip_address: Optional[str] = 'unknown_ip'
    user_id: Optional[str] = 'unknown_user'

class ChatResponse(BaseModel):
    response: str
    context_sources: List[str] = []
    type: str = 'text'
    function_call: Optional[Dict[str, Any]] = None

class UpdatePromptRequest(BaseModel):
    system_prompt: str

@chatbot_router.get('/prompts', response_model=Dict[str, Any])
async def get_prompts():
    return prompt_manager.get_all_prompts()

@chatbot_router.post('/prompts/{context_type}')
async def update_prompt(context_type: str, request: UpdatePromptRequest):
    success = prompt_manager.update_prompt(context_type, request.system_prompt)
    if not success:
        raise HTTPException(status_code=400, detail='Context type not found or save failed')
    return {'status': 'success', 'message': f'Updated prompt for {context_type}'}

@chatbot_router.post('/upload-doc')
async def upload_documents(files: List[UploadFile]=File(...)):
    results = []
    total_chunks = 0
    for file in files:
        try:
            text = await file_processor.process_file(file)
            if not text:
                results.append({'filename': file.filename, 'status': 'failed', 'reason': 'Empty or unsupported'})
                continue
            chunks = file_processor.chunk_text(text)
            file_chunk_count = 0
            for chunk in chunks:
                success = await vector_store.add_document(chunk, file.filename)
                if success:
                    file_chunk_count += 1
            total_chunks += file_chunk_count
            results.append({'filename': file.filename, 'status': 'success', 'chunks': file_chunk_count})
        except Exception as e:
            logger.error(f'Error processing {file.filename}: {e}')
            results.append({'filename': file.filename, 'status': 'error', 'message': str(e)})
    return {'status': 'completed', 'files': results, 'total_chunks_stored': total_chunks}

@chatbot_router.post('/chat', response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        relevant_docs = []
        if request.school_code and request.context_type == 'rag':
            logger.info(f"🔍 Chat RAG: Searching for code='{request.school_code}', query='{request.message}'")
            try:
                relevant_docs = await vector_store.search(request.message, school_code=request.school_code, limit=10)
                logger.info(f'✅ Chat RAG: Found {len(relevant_docs)} docs')
                for i, d in enumerate(relevant_docs):
                    snippet = d.get('content', '')[:100].replace('\n', ' ')
                    logger.info(f"   Doc {i + 1}: {d.get('filename')} -> {snippet}...")
            except Exception as e:
                logger.error(f'❌ Chat RAG Search Error: {e}')
        else:
            logger.warning('Chat request missing school_code, skipping RAG retrieval')
        context_str = ''
        sources = []
        if relevant_docs:
            context_str = '\n'.join([f"--- Nguồn: {d['filename']} ---\n{d['content']}" for d in relevant_docs])
            sources = list(set([d['filename'] for d in relevant_docs]))
        system_base = prompt_manager.get_system_prompt(request.context_type)
        full_system_instruction = system_base
        if context_str:
            full_system_instruction = f'\n{system_base}\n\n=== DỮ LIỆU THAM KHẢO (Được tìm thấy trong tài liệu của người dùng) ===\n{context_str}\n======================================================================\nHÃY ƯU TIÊN SỬ DỤNG DỮ LIỆU THAM KHẢO TRÊN ĐỂ TRẢ LỜI CÂU HỎI.\nNếu thông tin không có trong tài liệu, hãy sử dụng kiến thức của bạn nhưng hãy nói rõ.\n'
        if request.tools:
            result = await gemini_client.chat_with_tools(prompt=request.message, tools=request.tools, history=request.history, system_instruction=full_system_instruction)
            if result.get('type') == 'function_call':
                return ChatResponse(response='', context_sources=sources, type='function_call', function_call=result.get('function_call'))
            response_text = result.get('content', '')
        else:
            response_text = await gemini_client.chat(prompt=request.message, system_instruction=full_system_instruction, history=request.history)

        async def background_safety_check():
            try:
                safety_result = await gemini_client.check_content_safety(request.message)
                if not safety_result.get('is_safe'):
                    category = safety_result.get('category', 'Unknown')
                    reason = safety_result.get('reason', '')
                    vector_store.log_flagged_content(service_name=request.service_name, ip_address=request.ip_address, user_identifier=request.user_id, content=request.message, category=category, reason=reason)
                    alert_msg = f"🚨 **PHÁT HIỆN NỘI DUNG VI PHẠM** 🚨\n\n📂 **Nhóm:** {category}\n📝 **Nội dung:** {request.message}\n🔌 **Service:** {request.service_name}\n👤 **User:** {request.user_id}\n🌍 **IP:** {request.ip_address}\n💡 **Lý do:** {reason}\n🕒 **Thời gian:** {(start_time if 'start_time' in locals() else 'N/A')}"
                    try:
                        await telegram_bot.send_message(alert_msg)
                    except:
                        pass
            except Exception as e:
                logger.error(f'Background safety check failed: {e}')
        asyncio.create_task(background_safety_check())
        return ChatResponse(response=response_text, context_sources=sources)
    except Exception as e:
        logger.error(f'Chat error: {str(e)}')
        raise HTTPException(status_code=500, detail=f'AI Service Error: {str(e)}')

@chatbot_router.post('/ai-hub/vectorize')
async def ai_hub_vectorize(file: UploadFile=File(...), webhook_url: Optional[str]=Form(None), metadata: Optional[str]=Form(None), enable_summary: bool=Form(False), enable_classification: bool=Form(False)):
    try:
        meta_dict = {}
        if metadata:
            try:
                meta_dict = json.loads(metadata)
            except:
                logger.warning(f'Invalid metadata JSON: {metadata}')
        file_bytes = await file.read()
        task_id = await ai_hub_service.enqueue_task(file_bytes=file_bytes, filename=file.filename, webhook_url=webhook_url, metadata=meta_dict, enable_summary=enable_summary, enable_classification=enable_classification)
        return {'status': 'queued', 'task_id': task_id, 'message': f'File {file.filename} đã được đưa vào hàng đợi xử lý.'}
    except Exception as e:
        logger.error(f'AI Hub Error: {e}')
        raise HTTPException(status_code=500, detail=str(e))

@chatbot_router.get('/ai-hub/tasks/{task_id}')
async def get_ai_hub_task_status(task_id: str):
    task = task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail='Task not found')
    return task

@chatbot_router.get('/admin/flagged')
async def get_flagged_content(limit: int=50):
    return vector_store.get_flagged_content(limit=limit)

@chatbot_router.delete('/admin/flagged/{id}')
async def delete_flagged_content(id: int):
    success = vector_store.delete_flagged_content(id)
    if not success:
        raise HTTPException(status_code=404, detail='Not found or failed to delete')
    return {'status': 'success'}

@chatbot_router.get('/ai-hub/readiness')
async def ai_hub_readiness():
    from datetime import datetime, timezone
    from .llm_client import gemini_client
    from .groq_client import groq_client
    gemini_available = 0
    gemini_total = 0
    gemini_status = 'unavailable'
    gemini_cooldown = 0
    try:
        if gemini_client and gemini_client.rate_limiter:
            status = gemini_client.rate_limiter.get_availability_status()
            gemini_available = status.get('available_keys', 0)
            gemini_total = status.get('total_keys', 0)
            gemini_status = status.get('status', 'unavailable')
            gemini_cooldown = status.get('avg_cooldown_remaining', 0)
    except Exception as e:
        logger.error(f'Error getting Gemini status: {e}')
    groq_available = 0
    groq_total = 0
    groq_status = 'unavailable'
    groq_cooldown = 0
    try:
        if groq_client:
            status = groq_client.get_availability_status()
            groq_available = status.get('available_keys', 0)
            groq_total = status.get('total_keys', 0)
            groq_status = status.get('status', 'unavailable')
            groq_cooldown = status.get('avg_cooldown_remaining', 0)
    except Exception as e:
        logger.error(f'Error getting Groq status: {e}')
    total_available = gemini_available + groq_available
    total_keys = gemini_total + groq_total
    gemini_ok = gemini_status in ['ok', 'low']
    groq_ok = groq_status in ['ok', 'low']
    if gemini_status == 'ok':
        overall_status = 'accepting'
        reason = None
        ready = True
        accepting = True
        retry_after = None
    elif gemini_status == 'low' or (gemini_status == 'exhausted' and groq_ok):
        overall_status = 'degraded'
        reason = 'Quota thấp, đề nghị giảm tốc độ upload'
        ready = True
        accepting = True
        retry_after = None
    elif groq_ok:
        overall_status = 'degraded'
        reason = 'Đang sử dụng fallback, tốc độ có thể chậm'
        ready = True
        accepting = True
        retry_after = None
    else:
        overall_status = 'unavailable'
        reason = 'Hết quota API, vui lòng thử lại sau'
        ready = False
        accepting = False
        max_cooldown = max(gemini_cooldown, groq_cooldown)
        retry_after = int(max_cooldown) if max_cooldown > 0 else 60
    response_data = {'ready': ready, 'accepting_requests': accepting, 'status': overall_status, 'reason': reason, 'quota_available': total_available, 'quota_total': total_keys, 'retry_after': retry_after, 'timestamp': datetime.now(timezone.utc).isoformat()}
    if not ready:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=response_data, headers={'Retry-After': str(retry_after)})
    return response_data