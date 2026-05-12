import os
from huggingface_hub import snapshot_download
BACKBONE_REPO = 'pnnbao-ump/VieNeu-TTS-q4-gguf'
CODEC_REPO = 'neuphonic/neucodec'
BASE_DIR = '/app/resource/models/vieneu'
BACKBONE_DIR = os.path.join(BASE_DIR, 'backbone')
CODEC_DIR = os.path.join(BASE_DIR, 'codec')

def download_model(repo_id, target_dir):
    print(f'Downloading {repo_id} to {target_dir}...')
    try:
        os.makedirs(target_dir, exist_ok=True)
        path = snapshot_download(repo_id=repo_id, local_dir=target_dir, allow_patterns=['*.onnx', '*.gguf', '*.json', '*.yaml', '*.md', '*.bin', '*.safetensors', '*.pt', '*.pth'], ignore_patterns=['*.git*'])
        print(f'✅ Download complete! Files saved to: {path}')
        print(f'   Contents: {os.listdir(path)}')
        return path
    except Exception as e:
        print(f'❌ Error downloading {repo_id}: {e}')
        return None
if __name__ == '__main__':
    print('🚀 Starting download of VieNeu-TTS models...')
    download_model(BACKBONE_REPO, BACKBONE_DIR)
    download_model(CODEC_REPO, CODEC_DIR)
    print('🎉 All downloads finished.')