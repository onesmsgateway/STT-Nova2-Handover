import asyncio
import time
import logging
from typing import Dict, List, Optional
from collections import defaultdict
from threading import Lock
logger = logging.getLogger(__name__)

class GeminiRateLimiter:

    def __init__(self, api_keys: List[str], rpm_per_key: int=15):
        self.api_keys = api_keys
        self.rpm_per_key = rpm_per_key
        self.lock = Lock()
        self.key_requests: Dict[str, List[float]] = defaultdict(list)
        self.key_cooldowns: Dict[str, float] = {}
        self.current_key_index = 0
        self.last_request_time = 0.0
        self.min_delay = 60.0 / (len(api_keys) * rpm_per_key) if api_keys else 1.0
        logger.info(f'🔧 RateLimiter initialized: {len(api_keys)} keys, {rpm_per_key} RPM/key, {self.min_delay:.2f}s min delay')

    def _cleanup_old_requests(self, key: str, window_seconds: float=60.0):
        now = time.time()
        cutoff = now - window_seconds
        self.key_requests[key] = [t for t in self.key_requests[key] if t > cutoff]

    def _get_key_request_count(self, key: str) -> int:
        self._cleanup_old_requests(key)
        return len(self.key_requests[key])

    def _is_key_available(self, key: str) -> bool:
        now = time.time()
        if key in self.key_cooldowns:
            if now < self.key_cooldowns[key]:
                return False
            else:
                del self.key_cooldowns[key]
        return self._get_key_request_count(key) < self.rpm_per_key

    def set_key_cooldown(self, key: str, seconds: float):
        with self.lock:
            self.key_cooldowns[key] = time.time() + seconds
            logger.warning(f'⏸️ Key {key[:8]}... in cooldown for {seconds:.1f}s')

    def get_next_available_key(self) -> Optional[str]:
        with self.lock:
            if not self.api_keys:
                return None
            for _ in range(len(self.api_keys)):
                key = self.api_keys[self.current_key_index]
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                if self._is_key_available(key):
                    return key
            min_key = min(self.api_keys, key=lambda k: self._get_key_request_count(k))
            return min_key

    def record_request(self, key: str):
        with self.lock:
            self.key_requests[key].append(time.time())
            self.last_request_time = time.time()

    async def wait_for_capacity(self):
        with self.lock:
            now = time.time()
            time_since_last = now - self.last_request_time
            wait_time = max(0, self.min_delay - time_since_last)
        if wait_time > 0:
            await asyncio.sleep(wait_time)

    def get_stats(self) -> Dict:
        with self.lock:
            stats = {'total_keys': len(self.api_keys), 'rpm_per_key': self.rpm_per_key, 'min_delay': self.min_delay, 'keys': {}}
            for key in self.api_keys:
                key_short = key[:8] + '...'
                stats['keys'][key_short] = {'requests_last_minute': self._get_key_request_count(key), 'available': self._is_key_available(key), 'cooldown_remaining': max(0, self.key_cooldowns.get(key, 0) - time.time())}
            return stats

    def get_availability_status(self) -> Dict:
        with self.lock:
            if not self.api_keys:
                return {'available_keys': 0, 'total_keys': 0, 'status': 'unavailable', 'avg_cooldown_remaining': 0}
            available_count = 0
            total_cooldown = 0.0
            now = time.time()
            for key in self.api_keys:
                if self._is_key_available(key):
                    available_count += 1
                else:
                    cooldown_end = self.key_cooldowns.get(key, now)
                    total_cooldown += max(0, cooldown_end - now)
            unavailable_count = len(self.api_keys) - available_count
            avg_cooldown = total_cooldown / unavailable_count if unavailable_count > 0 else 0
            if available_count == 0:
                status = 'exhausted'
            elif available_count < len(self.api_keys) * 0.3:
                status = 'low'
            else:
                status = 'ok'
            return {'available_keys': available_count, 'total_keys': len(self.api_keys), 'status': status, 'avg_cooldown_remaining': round(avg_cooldown, 1)}
rate_limiter: Optional[GeminiRateLimiter] = None

def get_rate_limiter() -> Optional[GeminiRateLimiter]:
    return rate_limiter

def init_rate_limiter(api_keys: List[str], rpm_per_key: int=15) -> GeminiRateLimiter:
    global rate_limiter
    rate_limiter = GeminiRateLimiter(api_keys, rpm_per_key)
    return rate_limiter