from typing import List

class BaseAPIKeyManager:

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.total_keys = len(api_keys)
        self.current_index = 0

    def get_current_key(self) -> str:
        if not self.api_keys:
            raise ValueError('No API keys available')
        return self.api_keys[self.current_index]

    def get_key_info(self) -> str:
        return f'Key {self.current_index + 1}/{self.total_keys}'

    def rotate_key(self) -> str:
        if not self.api_keys:
            raise ValueError('No API keys available')
        self.current_index = (self.current_index + 1) % self.total_keys
        return self.get_current_key()

    def has_keys(self) -> bool:
        return len(self.api_keys) > 0