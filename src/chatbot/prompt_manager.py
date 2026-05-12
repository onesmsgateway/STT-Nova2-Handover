import json
import os
import logging
from typing import Dict, Any
logger = logging.getLogger(__name__)

class PromptManager:

    def __init__(self, prompts_file: str='src/chatbot/prompts.json'):
        self.prompts_file = prompts_file
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.prompts_file):
                with open(self.prompts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f'❌ Error loading prompts: {e}')
        return {'general': {'system_prompt': 'Bạn là trợ lý ảo.', 'description': 'Mặc định (Fallback)'}}

    def get_system_prompt(self, context_type: str) -> str:
        self.prompts = self._load_prompts()
        context_data = self.prompts.get(context_type, self.prompts.get('general'))
        return context_data.get('system_prompt', '')

    def update_prompt(self, context_type: str, new_prompt: str) -> bool:
        try:
            self.prompts = self._load_prompts()
            if context_type in self.prompts:
                self.prompts[context_type]['system_prompt'] = new_prompt
                with open(self.prompts_file, 'w', encoding='utf-8') as f:
                    json.dump(self.prompts, f, ensure_ascii=False, indent=4)
                return True
            return False
        except Exception as e:
            logger.error(f'❌ Error saving prompt: {e}')
            return False

    def get_all_prompts(self) -> Dict[str, Any]:
        self.prompts = self._load_prompts()
        return self.prompts
prompt_manager = PromptManager()