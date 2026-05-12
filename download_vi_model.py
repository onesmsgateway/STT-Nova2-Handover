from huggingface_hub import snapshot_download
import os

def download_vixtts():
    model_id = 'capleaf/viXTTS'
    local_dir = '/app/resource/models/vixtts'
    print(f'Downloading {model_id} to {local_dir}...')
    try:
        snapshot_download(repo_id=model_id, local_dir=local_dir)
        print('✅ Download complete.')
    except Exception as e:
        print(f'❌ Download failed: {e}')
if __name__ == '__main__':
    download_vixtts()