import os
import logging
from config import ENGINE, DEBUG_MODE
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def preload_models():
    logger.info('🚀 Bắt đầu pre-load models...')
    try:
        if ENGINE == 'phowhisper':
            logger.info('📦 Pre-loading PhoWhisper model...')
            from phowhisper_engine import _init_pipeline
            _init_pipeline()
            logger.info('✅ PhoWhisper model đã được pre-load thành công!')
        else:
            logger.info(f'ℹ️ Engine hiện tại: {ENGINE} - không cần pre-load')
    except Exception as e:
        logger.error(f'❌ Lỗi pre-load models: {e}')
        pass
    logger.info('🏁 Hoàn thành pre-load models')
if __name__ == '__main__':
    preload_models()