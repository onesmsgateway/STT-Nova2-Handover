import time
import asyncio
import gc
from typing import Optional, Any
from src.core.logger import setup_logger
logger = setup_logger(__name__)

class SmartModelManager:

    def __init__(self, model_loader_func, idle_timeout: int=1800):
        self.loader = model_loader_func
        self.timeout = idle_timeout
        self.model: Optional[Any] = None
        self.last_used_time = 0
        self.lock = asyncio.Lock()
        self._maintenance_task: Optional[asyncio.Task] = None
        self.is_loading = False

    async def get_model(self):
        async with self.lock:
            self.last_used_time = time.time()
            if self.model is None:
                logger.info('🧠 SmartModel: Loading heavy model into RAM...')
                self.is_loading = True
                try:
                    if asyncio.iscoroutinefunction(self.loader):
                        self.model = await self.loader()
                    else:
                        self.model = self.loader()
                    logger.info('✅ SmartModel: Model loaded successfully!')
                    if not self._maintenance_task or self._maintenance_task.done():
                        self._maintenance_task = asyncio.create_task(self._maintenance_loop())
                except Exception as e:
                    logger.error(f'❌ SmartModel: Failed to load model: {e}')
                    raise
                finally:
                    self.is_loading = False
            return self.model

    async def _maintenance_loop(self):
        logger.info('⏳ SmartModel: Maintenance loop started')
        while True:
            await asyncio.sleep(60)
            async with self.lock:
                if self.model:
                    idle_time = time.time() - self.last_used_time
                    if idle_time > self.timeout:
                        logger.info(f'💤 SmartModel: Model idle for {idle_time:.1f}s. Unloading to free RAM...')
                        self._unload_model()
                        break

    def _unload_model(self):
        try:
            if hasattr(self.model, 'cpu'):
                self.model.cpu()
            del self.model
            self.model = None
            gc.collect()
            logger.info('🧹 SmartModel: RAM freed')
        except Exception as e:
            logger.error(f'⚠️ SmartModel: Error during unload: {e}')