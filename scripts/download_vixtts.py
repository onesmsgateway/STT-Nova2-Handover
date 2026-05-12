import os
from huggingface_hub import snapshot_download
MODEL_ID = 'capleaf/viXTTS'
TARGET_DIR = '/app/resource/models/vixtts'
print(f'Downloading {MODEL_ID} to {TARGET_DIR}...')
try:
    os.makedirs(TARGET_DIR, exist_ok=True)
    path = snapshot_download(repo_id=MODEL_ID, local_dir=TARGET_DIR)
    print(f'Download complete! Files saved to: {path}')
    print(f'Contents: {os.listdir(path)}')
except Exception as e:
    print(f'Error downloading model: {e}')