import os
import subprocess
import tempfile
import logging
from typing import Any, Dict, Optional
from transformers import pipeline
from config import PHOWHISPER_MODEL, PHOWHISPER_CHUNK_S, PHOWHISPER_STRIDE_LEFT_S, PHOWHISPER_STRIDE_RIGHT_S, PHOWHISPER_DEVICE, PHOWHISPER_CACHE_DIR, DEBUG_MODE
logger = logging.getLogger(__name__)
_PIPELINE = None

def _ensure_cache_dir() -> None:
    os.makedirs(PHOWHISPER_CACHE_DIR, exist_ok=True)
    os.environ.setdefault('HF_HOME', PHOWHISPER_CACHE_DIR)
    os.environ.setdefault('TRANSFORMERS_CACHE', PHOWHISPER_CACHE_DIR)
    os.environ.setdefault('HF_HUB_DOWNLOAD_TIMEOUT', '300')
    os.environ.setdefault('HF_HUB_DOWNLOAD_RETRIES', '3')
    if DEBUG_MODE:
        logger.info(f'📁 Cache directory: {PHOWHISPER_CACHE_DIR}')
        logger.info(f"⏱️ HF timeout: {os.environ.get('HF_HUB_DOWNLOAD_TIMEOUT')}s")

def _init_pipeline():
    global _PIPELINE
    if _PIPELINE is not None:
        if DEBUG_MODE:
            logger.info('🔄 PhoWhisper pipeline đã được khởi tạo, sử dụng lại')
        return _PIPELINE
    if DEBUG_MODE:
        logger.info(f'🚀 Bắt đầu khởi tạo PhoWhisper pipeline: {PHOWHISPER_MODEL}')
    _ensure_cache_dir()
    device_index = -1
    try:
        _PIPELINE = pipeline(task='automatic-speech-recognition', model=PHOWHISPER_MODEL, chunk_length_s=PHOWHISPER_CHUNK_S, stride_length_s=(PHOWHISPER_STRIDE_LEFT_S, PHOWHISPER_STRIDE_RIGHT_S), device=device_index, return_timestamps=True)
        _PIPELINE.model.config.forced_decoder_ids = _PIPELINE.tokenizer.get_decoder_prompt_ids(language='vietnamese', task='transcribe')
        if DEBUG_MODE:
            logger.info('✅ PhoWhisper pipeline khởi tạo thành công!')
        return _PIPELINE
    except Exception as e:
        logger.error(f'❌ Lỗi khởi tạo PhoWhisper pipeline: {e}')
        raise

def _ffmpeg_resample(input_path: str, output_path: str) -> bool:
    cmd = ['ffmpeg', '-y', '-i', input_path, '-ac', '1', '-ar', '16000', output_path]
    try:
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    except Exception:
        return False

def _download_to_tmp(url: str) -> Optional[str]:
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.wav')
    os.close(tmp_fd)
    try:
        ok = _ffmpeg_resample(url, tmp_path)
        if not ok:
            return None
        return tmp_path
    except Exception:
        return None

def unload_model():
    global _PIPELINE
    if _PIPELINE is not None:
        del _PIPELINE
        _PIPELINE = None
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        if DEBUG_MODE:
            logger.info('🧹 PhoWhisper model unloaded')

def transcribe(url_or_path: str, pipeline_instance=None) -> Dict[str, Any]:
    if DEBUG_MODE:
        logger.info(f'🎤 Bắt đầu transcribe: {url_or_path}')
    pipe = pipeline_instance if pipeline_instance is not None else _init_pipeline()
    cleanup_path = None
    local_path = url_or_path
    if url_or_path.startswith(('http://', 'https://')):
        if DEBUG_MODE:
            logger.info(f'📥 Tải audio từ URL: {url_or_path}')
        local_path = _download_to_tmp(url_or_path)
        cleanup_path = local_path
        if not local_path:
            return {'success': False, 'message': 'Không thể tải/chuẩn hóa audio bằng ffmpeg'}
    try:
        if DEBUG_MODE:
            logger.info(f'🔄 Bắt đầu transcribe với PhoWhisper: {local_path}')
        result = pipe(local_path)
        text = result.get('text', '')
        timestamps = result.get('chunks') or result.get('timestamps')
        if DEBUG_MODE:
            logger.info(f'✅ Transcribe hoàn thành: {len(text)} ký tự')
        return {'success': True, 'transcript': text or '', 'timestamps': timestamps or [], 'raw': result}
    except Exception as e:
        logger.error(f'❌ Lỗi transcribe: {e}')
        return {'success': False, 'message': str(e)}
    finally:
        if cleanup_path and os.path.exists(cleanup_path):
            try:
                os.remove(cleanup_path)
                if DEBUG_MODE:
                    logger.info(f'🧹 Đã xóa file tạm: {cleanup_path}')
            except Exception:
                pass