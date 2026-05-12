import os
import requests
import uuid
from typing import Optional
import mimetypes
from urllib.parse import urlparse
from pathlib import Path
from src.core.logger import setup_logger
from src.core.exceptions import DownloadError
logger = setup_logger(__name__)

class Downloader:

    def __init__(self, save_dir: str='downloads'):
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)

    def download_file(self, url: str) -> str:
        try:
            if os.path.exists(url):
                return os.path.abspath(url)
            parsed_url = urlparse(url)
            if not parsed_url.scheme or parsed_url.scheme == 'file':
                path = parsed_url.path
                if os.path.exists(path):
                    return os.path.abspath(path)
                raise DownloadError(f'Local file not found: {path}')
            try:
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                content_type = response.headers.get('content-type', '')
                ext = mimetypes.guess_extension(content_type)
                if not ext:
                    path = parsed_url.path
                    ext = os.path.splitext(path)[1]
                if not ext:
                    ext = '.mp3'
                filename = f'{uuid.uuid4()}{ext}'
                file_path = os.path.join(self.save_dir, filename)
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                logger.info(f'✅ Downloaded: {url} -> {file_path}')
                return os.path.abspath(file_path)
            except requests.RequestException as e:
                raise DownloadError(f'Network error downloading {url}: {e}')
        except Exception as e:
            logger.error(f'❌ Download failed: {e}')
            raise DownloadError(f'Failed to download {url}: {e}')

    def cleanup(self, items: list[str]):
        for item in items:
            try:
                if os.path.exists(item):
                    os.remove(item)
                    logger.debug(f'Deleted: {item}')
            except Exception as e:
                logger.warning(f'Failed to delete {item}: {e}')