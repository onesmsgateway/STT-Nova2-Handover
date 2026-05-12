import os
import logging
from typing import List
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
logger = logging.getLogger(__name__)

def get_list_from_env(key: str, default: List[str]=None) -> List[str]:
    val = os.getenv(key)
    if not val:
        return default or []
    return [x.strip() for x in val.split(',') if x.strip()]
DEEPGRAM_API_KEYS = get_list_from_env('DEEPGRAM_API_KEYS')
if not DEEPGRAM_API_KEYS:
    DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY', '')
    if DEEPGRAM_API_KEY:
        DEEPGRAM_API_KEYS = [DEEPGRAM_API_KEY]
    else:
        logger.warning('⚠️ No DEEPGRAM_API_KEYS found in environment variables!')
else:
    DEEPGRAM_API_KEY = DEEPGRAM_API_KEYS[0]
GOOGLE_API_KEYS = get_list_from_env('GOOGLE_API_KEYS')
if not GOOGLE_API_KEYS:
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
    if GOOGLE_API_KEY:
        GOOGLE_API_KEYS = [GOOGLE_API_KEY]
else:
    GOOGLE_API_KEY = GOOGLE_API_KEYS[0]
GOOGLE_CLASSIFICATION_API_KEYS = get_list_from_env('GOOGLE_CLASSIFICATION_API_KEYS')
if not GOOGLE_CLASSIFICATION_API_KEYS:
    GOOGLE_CLASSIFICATION_API_KEYS = GOOGLE_API_KEYS
MAX_WORDS = int(os.getenv('MAX_WORDS', '150'))
AUDIO_PROCESSING_MODE = os.getenv('AUDIO_PROCESSING_MODE', 'auto')
DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
DISABLE_TRIM = os.getenv('DISABLE_TRIM', 'False').lower() == 'true'
MIN_DURATION_THRESHOLD = int(os.getenv('MIN_DURATION_THRESHOLD', '10'))
DEEPGRAM_MODEL = os.getenv('DEEPGRAM_MODEL', 'nova-2')
GOOGLE_AI_MODEL = os.getenv('GOOGLE_AI_MODEL', 'gemini-2.0-flash')
ENGINE = os.getenv('STT_ENGINE', 'deepgram')
PHOWHISPER_ENABLED = True
PHOWHISPER_MODEL = os.getenv('PHOWHISPER_MODEL', 'vinai/PhoWhisper-small')
PHOWHISPER_CHUNK_S = int(os.getenv('PHOWHISPER_CHUNK_S', '30'))
PHOWHISPER_STRIDE_LEFT_S = int(os.getenv('PHOWHISPER_STRIDE_LEFT_S', '5'))
PHOWHISPER_STRIDE_RIGHT_S = int(os.getenv('PHOWHISPER_STRIDE_RIGHT_S', '5'))
PHOWHISPER_DEVICE = os.getenv('PHOWHISPER_DEVICE', 'cpu')
PHOWHISPER_CACHE_DIR = os.getenv('PHOWHISPER_CACHE_DIR', '/app/.cache/hf')
import multiprocessing
try:
    _default_workers = min(4, multiprocessing.cpu_count())
except:
    _default_workers = 2
MAX_WORKER_PROCESSES = int(os.getenv('MAX_WORKER_PROCESSES', str(_default_workers)))
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_ADMIN_CHAT_ID = int(os.getenv('TELEGRAM_ADMIN_CHAT_ID', '-4927910447'))
TELEGRAM_BOT_ENABLED = bool(TELEGRAM_BOT_TOKEN)
TELEGRAM_NOTIFY_STARTUP = True
TELEGRAM_NOTIFY_ERRORS = True
TELEGRAM_NOTIFY_PROCESSING = False
URL_DELAY = 2
QUEUE_FILE = 'queue_data/url_queue.txt'
STATUS_FILE = 'queue_data/processing_status.json'
IN_PROGRESS_FILE = 'queue_data/in_progress.json'
DEAD_LETTER_FILE = 'queue_data/dead_letter.json'
REQUEST_TIMEOUT = 300
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = 3
AUTO_RESUME_QUEUE = os.getenv('AUTO_RESUME_QUEUE', 'True').lower() == 'true'
VECTOR_DB_USER = os.getenv('VECTOR_DB_USER', 'conek_ai')
VECTOR_DB_PASSWORD = os.getenv('VECTOR_DB_PASSWORD', 'conek_ai_password')
VECTOR_DB_HOST = os.getenv('VECTOR_DB_HOST', 'vector-db')
VECTOR_DB_PORT = os.getenv('VECTOR_DB_PORT', '5432')
VECTOR_DB_NAME = os.getenv('VECTOR_DB_NAME', 'vector_db')
WEBHOOK_DOMAIN_MAPPING = {}
_mapping_str = os.getenv('WEBHOOK_DOMAIN_MAPPING', '')
if _mapping_str:
    try:
        for pair in _mapping_str.split(','):
            if '=' in pair:
                k, v = pair.split('=', 1)
                WEBHOOK_DOMAIN_MAPPING[k.strip()] = v.strip()
    except Exception as e:
        logger.error(f'Failed to parse WEBHOOK_DOMAIN_MAPPING: {e}')
POSTGRESQL_ENABLED = os.getenv('POSTGRESQL_ENABLED', 'true').lower() == 'true'
POSTGRESQL_HOST = os.getenv('POSTGRESQL_HOST', 'host.docker.internal')
POSTGRESQL_PORT = int(os.getenv('POSTGRESQL_PORT', '5432'))
POSTGRESQL_DATABASE = os.getenv('POSTGRESQL_DATABASE', 'fusionpbx')
POSTGRESQL_USERNAME = os.getenv('POSTGRESQL_USERNAME', 'fusionpbx')
POSTGRESQL_PASSWORD = os.getenv('POSTGRESQL_PASSWORD', '')
POSTGRESQL_POOL_SIZE = 5
POSTGRESQL_MAX_OVERFLOW = 10
POSTGRESQL_POOL_TIMEOUT = 30
POSTGRESQL_POOL_RECYCLE = 3600
import urllib.parse
POSTGRESQL_PASSWORD_ESCAPED = urllib.parse.quote_plus(POSTGRESQL_PASSWORD)
POSTGRESQL_CONNECTION_STRING = f'postgresql://{POSTGRESQL_USERNAME}:{POSTGRESQL_PASSWORD_ESCAPED}@{POSTGRESQL_HOST}:{POSTGRESQL_PORT}/{POSTGRESQL_DATABASE}'
POSTGRESQL_TABLE_CDR = 'cdr'