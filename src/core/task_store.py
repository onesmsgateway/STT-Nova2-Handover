import json
import threading
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
logger = logging.getLogger(__name__)

class TaskStore:

    def __init__(self, storage_path='queue_data/tasks.json'):
        self.storage_path = storage_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        self.tasks = self._load_tasks()
        self.lock = threading.Lock()

    def _load_tasks(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f'Failed to load task store: {e}')
                return {}
        return {}

    def _save_tasks(self):
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f'Failed to save task store: {e}')

    def create_task(self, task_id: str, data: Dict[str, Any]):
        with self.lock:
            self.tasks[task_id] = {**data, 'status': 'queued', 'progress': 0, 'created_at': datetime.now().isoformat(), 'updated_at': datetime.now().isoformat(), 'result': None}
            self._save_tasks()

    def update_task(self, task_id: str, status: Optional[str]=None, result: Any=None, progress: int=None):
        with self.lock:
            if task_id in self.tasks:
                if status:
                    self.tasks[task_id]['status'] = status
                if progress is not None:
                    self.tasks[task_id]['progress'] = progress
                if result is not None:
                    self.tasks[task_id]['result'] = result
                self.tasks[task_id]['updated_at'] = datetime.now().isoformat()
                self._save_tasks()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            return self.tasks.get(task_id)
task_store = TaskStore()