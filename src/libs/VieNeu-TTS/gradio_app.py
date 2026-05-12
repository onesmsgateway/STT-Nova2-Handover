import gradio as gr
print('⏳ Đang khởi động... Vui lòng chờ...')
import soundfile as sf
import tempfile
import torch
from vieneu_tts import VieNeuTTS, FastVieNeuTTS
import os
import time
import numpy as np
from typing import Generator, Optional, Tuple
import queue
import threading
import yaml
from utils.core_utils import split_text_into_chunks
from functools import lru_cache
import gc
print('⏳ Đang khởi động VieNeu-TTS...')
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        _config = yaml.safe_load(f) or {}
except Exception as e:
    raise RuntimeError(f'Không thể đọc config.yaml: {e}')
BACKBONE_CONFIGS = _config.get('backbone_configs', {})
CODEC_CONFIGS = _config.get('codec_configs', {})
VOICE_SAMPLES = _config.get('voice_samples', {})
_text_settings = _config.get('text_settings', {})
MAX_CHARS_PER_CHUNK = _text_settings.get('max_chars_per_chunk', 256)
MAX_TOTAL_CHARS_STREAMING = _text_settings.get('max_total_chars_streaming', 3000)
if not BACKBONE_CONFIGS or not CODEC_CONFIGS:
    raise ValueError('config.yaml thiếu backbone_configs hoặc codec_configs')
if not VOICE_SAMPLES:
    raise ValueError('config.yaml thiếu voice_samples')
tts = None
current_backbone = None
current_codec = None
model_loaded = False
using_lmdeploy = False
_ref_text_cache = {}

def should_use_lmdeploy(backbone_choice: str, device_choice: str) -> bool:
    if 'gguf' in backbone_choice.lower():
        return False
    if device_choice == 'Auto':
        has_gpu = torch.cuda.is_available()
    elif device_choice == 'CUDA':
        has_gpu = torch.cuda.is_available()
    else:
        has_gpu = False
    return has_gpu

@lru_cache(maxsize=32)
def get_ref_text_cached(text_path: str) -> str:
    with open(text_path, 'r', encoding='utf-8') as f:
        return f.read()

def cleanup_gpu_memory():
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    gc.collect()

def load_model(backbone_choice: str, codec_choice: str, device_choice: str, enable_triton: bool, max_batch_size: int):
    global tts, current_backbone, current_codec, model_loaded, using_lmdeploy
    lmdeploy_error_reason = None
    yield ('⏳ Đang tải model với tối ưu hóa... Lưu ý: Quá trình này sẽ tốn thời gian. Vui lòng kiên nhẫn.', gr.update(interactive=False), gr.update(interactive=False))
    try:
        if model_loaded and tts is not None:
            del tts
            cleanup_gpu_memory()
        backbone_config = BACKBONE_CONFIGS[backbone_choice]
        codec_config = CODEC_CONFIGS[codec_choice]
        use_lmdeploy = should_use_lmdeploy(backbone_choice, device_choice)
        if use_lmdeploy:
            lmdeploy_error_reason = None
            print(f'🚀 Using LMDeploy backend with optimizations')
            backbone_device = 'cuda'
            if 'ONNX' in codec_choice:
                codec_device = 'cpu'
            else:
                codec_device = 'cuda' if torch.cuda.is_available() else 'cpu'
            print(f'📦 Loading optimized model...')
            print(f"   Backbone: {backbone_config['repo']} on {backbone_device}")
            print(f"   Codec: {codec_config['repo']} on {codec_device}")
            print(f"   Triton: {('Enabled' if enable_triton else 'Disabled')}")
            print(f'   Max Batch Size: {max_batch_size}')
            try:
                tts = FastVieNeuTTS(backbone_repo=backbone_config['repo'], backbone_device=backbone_device, codec_repo=codec_config['repo'], codec_device=codec_device, memory_util=0.3, tp=1, enable_prefix_caching=True, enable_triton=enable_triton, max_batch_size=max_batch_size)
                using_lmdeploy = True
                print('📝 Pre-caching voice references...')
                for voice_name, voice_info in VOICE_SAMPLES.items():
                    audio_path = voice_info['audio']
                    text_path = voice_info['text']
                    if os.path.exists(audio_path) and os.path.exists(text_path):
                        ref_text = get_ref_text_cached(text_path)
                        tts.get_cached_reference(voice_name, audio_path, ref_text)
                print(f'   ✅ Cached {len(VOICE_SAMPLES)} voices')
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_str = str(e)
                if '$env:CUDA_PATH' in error_str:
                    lmdeploy_error_reason = 'Không tìm thấy biến môi trường CUDA_PATH. Vui lòng cài đặt NVIDIA GPU Computing Toolkit.'
                else:
                    lmdeploy_error_reason = f'{error_str}'
                yield (f'⚠️ LMDeploy Init Error: {lmdeploy_error_reason}. Đang loading model với backend mặc định - tốc độ chậm hơn so với lmdeploy...', gr.update(interactive=False), gr.update(interactive=False))
                time.sleep(1)
                use_lmdeploy = False
                using_lmdeploy = False
        if not use_lmdeploy:
            print(f'📦 Using original backend')
            if device_choice == 'Auto':
                if 'gguf' in backbone_choice.lower():
                    backbone_device = 'gpu' if torch.cuda.is_available() else 'cpu'
                else:
                    backbone_device = 'cuda' if torch.cuda.is_available() else 'cpu'
                if 'ONNX' in codec_choice:
                    codec_device = 'cpu'
                else:
                    codec_device = 'cuda' if torch.cuda.is_available() else 'cpu'
            else:
                backbone_device = device_choice.lower()
                codec_device = device_choice.lower()
                if 'ONNX' in codec_choice:
                    codec_device = 'cpu'
            if 'gguf' in backbone_choice.lower() and backbone_device == 'cuda':
                backbone_device = 'gpu'
            print(f'📦 Loading model...')
            print(f"   Backbone: {backbone_config['repo']} on {backbone_device}")
            print(f"   Codec: {codec_config['repo']} on {codec_device}")
            tts = VieNeuTTS(backbone_repo=backbone_config['repo'], backbone_device=backbone_device, codec_repo=codec_config['repo'], codec_device=codec_device)
            using_lmdeploy = False
        current_backbone = backbone_choice
        current_codec = codec_choice
        model_loaded = True
        backend_name = '🚀 LMDeploy (Optimized)' if using_lmdeploy else '📦 Standard'
        device_info = 'cuda' if use_lmdeploy else backbone_device if not use_lmdeploy else 'N/A'
        streaming_support = '✅ Có' if backbone_config['supports_streaming'] else '❌ Không'
        preencoded_note = '\n⚠️ Codec này cần sử dụng pre-encoded codes (.pt files)' if codec_config['use_preencoded'] else ''
        opt_info = ''
        if using_lmdeploy and hasattr(tts, 'get_optimization_stats'):
            stats = tts.get_optimization_stats()
            opt_info = f"\n\n🔧 Tối ưu hóa:\n  • Triton: {('✅' if stats['triton_enabled'] else '❌')}\n  • Max Batch Size: {max_batch_size}\n  • Reference Cache: {stats['cached_references']} voices\n  • Prefix Caching: ✅"
        warning_msg = ''
        if lmdeploy_error_reason:
            warning_msg = f'\n\n⚠️ **Cảnh báo:** Không thể kích hoạt LMDeploy (Optimized Backend) do lỗi sau:\n👉 {lmdeploy_error_reason}\n💡 Hệ thống đã tự động chuyển về chế độ Standard (chậm hơn).'
        success_msg = f'✅ Model đã tải thành công!\n\n🔧 Backend: {backend_name}\n🦜 Model Device: {device_info.upper()}\n🎵 Codec Device: {codec_device.upper()}{preencoded_note}\n🌊 Streaming: {streaming_support}{opt_info}{warning_msg}'
        yield (success_msg, gr.update(interactive=True), gr.update(interactive=True))
    except Exception as e:
        import traceback
        traceback.print_exc()
        model_loaded = False
        using_lmdeploy = False
        if '$env:CUDA_PATH' in str(e):
            yield ('❌ Lỗi khi tải model: Không tìm thấy biến môi trường CUDA_PATH. Vui lòng cài đặt NVIDIA GPU Computing Toolkit (https://developer.nvidia.com/cuda/toolkit)', gr.update(interactive=False), gr.update(interactive=True))
        else:
            yield (f'❌ Lỗi khi tải model: {str(e)}', gr.update(interactive=False), gr.update(interactive=True))
GGUF_ALLOWED_VOICES = ['Vĩnh (nam miền Nam)', 'Bình (nam miền Bắc)', 'Ngọc (nữ miền Bắc)', 'Dung (nữ miền Nam)', 'Nguyên (nam miền Nam)', 'Sơn (nam miền Nam)', 'Đoan (nữ miền Nam)', 'Tuyên (nam miền Bắc)']

def get_voice_options(backbone_choice: str):
    if 'gguf' in backbone_choice.lower():
        return [v for v in GGUF_ALLOWED_VOICES if v in VOICE_SAMPLES]
    return list(VOICE_SAMPLES.keys())

def update_voice_dropdown(backbone_choice: str, current_voice: str):
    options = get_voice_options(backbone_choice)
    new_value = current_voice if current_voice in options else options[0] if options else None
    return gr.update(choices=options, value=new_value)

def load_reference_info(voice_choice: str) -> Tuple[Optional[str], str]:
    if voice_choice in VOICE_SAMPLES:
        audio_path = VOICE_SAMPLES[voice_choice]['audio']
        text_path = VOICE_SAMPLES[voice_choice]['text']
        try:
            if os.path.exists(text_path):
                ref_text = get_ref_text_cached(text_path)
                return (audio_path, ref_text)
            else:
                return (audio_path, '⚠️ Không tìm thấy file text mẫu.')
        except Exception as e:
            return (None, f'❌ Lỗi: {str(e)}')
    return (None, '')

def synthesize_speech(text: str, voice_choice: str, custom_audio, custom_text: str, mode_tab: str, generation_mode: str, use_batch: bool):
    global tts, current_backbone, current_codec, model_loaded, using_lmdeploy
    if not model_loaded or tts is None:
        yield (None, '⚠️ Vui lòng tải model trước!')
        return
    if not text or text.strip() == '':
        yield (None, '⚠️ Vui lòng nhập văn bản!')
        return
    raw_text = text.strip()
    codec_config = CODEC_CONFIGS[current_codec]
    use_preencoded = codec_config['use_preencoded']
    if mode_tab == 'custom_mode':
        if custom_audio is None or not custom_text:
            yield (None, '⚠️ Thiếu Audio hoặc Text mẫu custom.')
            return
        ref_audio_path = custom_audio
        ref_text_raw = custom_text
        ref_codes_path = None
    else:
        if voice_choice not in VOICE_SAMPLES:
            yield (None, '⚠️ Vui lòng chọn giọng mẫu.')
            return
        ref_audio_path = VOICE_SAMPLES[voice_choice]['audio']
        text_path = VOICE_SAMPLES[voice_choice]['text']
        ref_codes_path = VOICE_SAMPLES[voice_choice]['codes']
        if not os.path.exists(ref_audio_path):
            yield (None, '❌ Không tìm thấy file audio mẫu.')
            return
        ref_text_raw = get_ref_text_cached(text_path)
    yield (None, '📄 Đang xử lý Reference...')
    try:
        if use_preencoded and ref_codes_path and os.path.exists(ref_codes_path):
            ref_codes = torch.load(ref_codes_path, map_location='cpu', weights_only=True)
        elif using_lmdeploy and hasattr(tts, 'get_cached_reference') and (mode_tab == 'preset_mode'):
            ref_codes = tts.get_cached_reference(voice_choice, ref_audio_path, ref_text_raw)
        else:
            ref_codes = tts.encode_reference(ref_audio_path)
        if isinstance(ref_codes, torch.Tensor):
            ref_codes = ref_codes.cpu().numpy()
    except Exception as e:
        yield (None, f'❌ Lỗi xử lý reference: {e}')
        return
    text_chunks = split_text_into_chunks(raw_text, max_chars=MAX_CHARS_PER_CHUNK)
    total_chunks = len(text_chunks)
    if generation_mode == 'Standard (Một lần)':
        backend_name = 'LMDeploy' if using_lmdeploy else 'Standard'
        batch_info = ' (Batch Mode)' if use_batch and using_lmdeploy and (total_chunks > 1) else ''
        batch_size_info = ''
        if use_batch and using_lmdeploy and hasattr(tts, 'max_batch_size'):
            batch_size_info = f' [Max batch: {tts.max_batch_size}]'
        yield (None, f'🚀 Bắt đầu tổng hợp {backend_name}{batch_info}{batch_size_info} ({total_chunks} đoạn)...')
        all_audio_segments = []
        sr = 24000
        silence_pad = np.zeros(int(sr * 0.15), dtype=np.float32)
        start_time = time.time()
        try:
            if use_batch and using_lmdeploy and hasattr(tts, 'infer_batch') and (total_chunks > 1):
                batch_size = tts.max_batch_size if hasattr(tts, 'max_batch_size') else 8
                num_batches = (total_chunks + batch_size - 1) // batch_size
                yield (None, f'⚡ Xử lý {num_batches} mini-batch(es) (max {batch_size} đoạn/batch)...')
                chunk_wavs = tts.infer_batch(text_chunks, ref_codes, ref_text_raw)
                for i, chunk_wav in enumerate(chunk_wavs):
                    if chunk_wav is not None and len(chunk_wav) > 0:
                        all_audio_segments.append(chunk_wav)
                        if i < total_chunks - 1:
                            all_audio_segments.append(silence_pad)
            else:
                for i, chunk in enumerate(text_chunks):
                    yield (None, f'⏳ Đang xử lý đoạn {i + 1}/{total_chunks}...')
                    chunk_wav = tts.infer(chunk, ref_codes, ref_text_raw)
                    if chunk_wav is not None and len(chunk_wav) > 0:
                        all_audio_segments.append(chunk_wav)
                        if i < total_chunks - 1:
                            all_audio_segments.append(silence_pad)
            if not all_audio_segments:
                yield (None, '❌ Không sinh được audio nào.')
                return
            yield (None, '💾 Đang ghép file và lưu...')
            final_wav = np.concatenate(all_audio_segments)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                sf.write(tmp.name, final_wav, sr)
                output_path = tmp.name
            process_time = time.time() - start_time
            backend_info = f" (Backend: {('LMDeploy 🚀' if using_lmdeploy else 'Standard 📦')})"
            speed_info = f', Tốc độ: {len(final_wav) / sr / process_time:.2f}x realtime' if process_time > 0 else ''
            yield (output_path, f'✅ Hoàn tất! (Thời gian: {process_time:.2f}s{speed_info}){backend_info}')
            if using_lmdeploy and hasattr(tts, 'cleanup_memory'):
                tts.cleanup_memory()
            cleanup_gpu_memory()
        except torch.cuda.OutOfMemoryError as e:
            cleanup_gpu_memory()
            yield (None, f"❌ GPU hết VRAM! Hãy thử:\n• Giảm Max Batch Size (hiện tại: {(tts.max_batch_size if hasattr(tts, 'max_batch_size') else 'N/A')})\n• Giảm độ dài văn bản\n\nChi tiết: {str(e)}")
            return
        except Exception as e:
            import traceback
            traceback.print_exc()
            cleanup_gpu_memory()
            yield (None, f'❌ Lỗi Standard Mode: {str(e)}')
            return
    else:
        sr = 24000
        crossfade_samples = int(sr * 0.03)
        audio_queue = queue.Queue(maxsize=100)
        PRE_BUFFER_SIZE = 3
        end_event = threading.Event()
        error_event = threading.Event()
        error_msg = ''

        def producer_thread():
            nonlocal error_msg
            try:
                previous_tail = None
                for i, chunk_text in enumerate(text_chunks):
                    stream_gen = tts.infer_stream(chunk_text, ref_codes, ref_text_raw)
                    for part_idx, audio_part in enumerate(stream_gen):
                        if audio_part is None or len(audio_part) == 0:
                            continue
                        if previous_tail is not None and len(previous_tail) > 0:
                            overlap = min(len(previous_tail), len(audio_part), crossfade_samples)
                            if overlap > 0:
                                fade_out = np.linspace(1.0, 0.0, overlap, dtype=np.float32)
                                fade_in = np.linspace(0.0, 1.0, overlap, dtype=np.float32)
                                blended = audio_part[:overlap] * fade_in + previous_tail[-overlap:] * fade_out
                                processed = np.concatenate([previous_tail[:-overlap] if len(previous_tail) > overlap else np.array([]), blended, audio_part[overlap:]])
                            else:
                                processed = np.concatenate([previous_tail, audio_part])
                            tail_size = min(crossfade_samples, len(processed))
                            previous_tail = processed[-tail_size:].copy()
                            output_chunk = processed[:-tail_size] if len(processed) > tail_size else processed
                        else:
                            tail_size = min(crossfade_samples, len(audio_part))
                            previous_tail = audio_part[-tail_size:].copy()
                            output_chunk = audio_part[:-tail_size] if len(audio_part) > tail_size else audio_part
                        if len(output_chunk) > 0:
                            audio_queue.put((sr, output_chunk))
                if previous_tail is not None and len(previous_tail) > 0:
                    audio_queue.put((sr, previous_tail))
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = str(e)
                error_event.set()
            finally:
                end_event.set()
                audio_queue.put(None)
        threading.Thread(target=producer_thread, daemon=True).start()
        yield ((sr, np.zeros(int(sr * 0.05))), '📄 Đang buffering...')
        pre_buffer = []
        while len(pre_buffer) < PRE_BUFFER_SIZE:
            try:
                item = audio_queue.get(timeout=5.0)
                if item is None:
                    break
                pre_buffer.append(item)
            except queue.Empty:
                if error_event.is_set():
                    yield (None, f'❌ Lỗi: {error_msg}')
                    return
                break
        full_audio_buffer = []
        backend_info = '🚀 LMDeploy' if using_lmdeploy else '📦 Standard'
        for sr, audio_data in pre_buffer:
            full_audio_buffer.append(audio_data)
            yield ((sr, audio_data), f'🔊 Đang phát ({backend_info})...')
        while True:
            try:
                item = audio_queue.get(timeout=0.05)
                if item is None:
                    break
                sr, audio_data = item
                full_audio_buffer.append(audio_data)
                yield ((sr, audio_data), f'🔊 Đang phát ({backend_info})...')
            except queue.Empty:
                if error_event.is_set():
                    yield (None, f'❌ Lỗi: {error_msg}')
                    break
                if end_event.is_set() and audio_queue.empty():
                    break
                continue
        if full_audio_buffer:
            final_wav = np.concatenate(full_audio_buffer)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                sf.write(tmp.name, final_wav, sr)
                yield (tmp.name, f'✅ Hoàn tất Streaming! ({backend_info})')
            if using_lmdeploy and hasattr(tts, 'cleanup_memory'):
                tts.cleanup_memory()
            cleanup_gpu_memory()

def batch_synthesize(text: str):
    global tts, model_loaded
    if not model_loaded or tts is None:
        return [None] * len(GGUF_ALLOWED_VOICES)
    raw_text = text.strip() or 'Chào bạn, đây là bản thử giọng mẫu.'
    chunk = raw_text[:100]
    results = []
    for voice_choice in GGUF_ALLOWED_VOICES:
        if voice_choice not in VOICE_SAMPLES:
            results.append(None)
            continue
        try:
            ref_audio_path = VOICE_SAMPLES[voice_choice]['audio']
            text_path = VOICE_SAMPLES[voice_choice]['text']
            ref_text_raw = get_ref_text_cached(text_path)
            ref_codes = tts.encode_reference(ref_audio_path)
            wav = tts.infer(chunk, ref_codes, ref_text_raw)
            if wav is not None and len(wav) > 0:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
                    import soundfile as sf
                    sf.write(tmp.name, wav, 24000)
                    results.append(tmp.name)
            else:
                results.append(None)
        except Exception as e:
            print(f'Batch preview error for {voice_choice}: {e}')
            results.append(None)
    return results
theme = gr.themes.Soft(primary_hue='indigo', secondary_hue='cyan', neutral_hue='slate', font=[gr.themes.GoogleFont('Inter'), 'ui-sans-serif', 'system-ui']).set(button_primary_background_fill='linear-gradient(90deg, #6366f1 0%, #0ea5e9 100%)', button_primary_background_fill_hover='linear-gradient(90deg, #4f46e5 0%, #0284c7 100%)')
css = '\n.container { max-width: 1400px; margin: auto; }\n.header-box {\n    text-align: center;\n    margin-bottom: 25px;\n    padding: 25px;\n    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);\n    border-radius: 12px;\n    color: white !important;\n}\n.header-title {\n    font-size: 2.5rem;\n    font-weight: 800;\n    color: white !important;\n}\n.gradient-text {\n    background: -webkit-linear-gradient(45deg, #60A5FA, #22D3EE);\n    -webkit-background-clip: text;\n    -webkit-text-fill-color: transparent;\n}\n.header-icon {\n    color: white;\n}\n.status-box {\n    font-weight: bold;\n    text-align: center;\n    border: none;\n    background: transparent;\n}\n.model-card-content {\n    display: flex;\n    flex-wrap: wrap;\n    justify-content: center;\n    align-items: center;\n    gap: 15px;\n    font-size: 0.9rem;\n    text-align: center;\n    color: white !important;\n}\n.model-card-item {\n    display: flex;\n    align-items: center;\n    justify-content: center;\n    gap: 6px;\n    color: white !important;\n}\n.model-card-item strong {\n    color: white !important;\n}\n.model-card-item span {\n    color: white !important;\n}\n.model-card-link {\n    color: #60A5FA;\n    text-decoration: none;\n    font-weight: 500;\n    transition: color 0.2s;\n}\n.model-card-link:hover {\n    color: #22D3EE;\n    text-decoration: underline;\n}\n'
EXAMPLES_LIST = [['Về miền Tây không chỉ để ngắm nhìn sông nước hữu tình, mà còn để cảm nhận tấm chân tình của người dân nơi đây.', 'Vĩnh (nam miền Nam)'], ['Hà Nội những ngày vào thu mang một vẻ đẹp trầm mặc và cổ kính đến lạ thường.', 'Bình (nam miền Bắc)']]
with gr.Blocks(theme=theme, css=css, title='VieNeu-TTS') as demo:
    with gr.Column(elem_classes='container'):
        gr.HTML('\n<div class="header-box">\n    <h1 class="header-title">\n        <span class="header-icon">🦜</span>\n        <span class="gradient-text">VieNeu-TTS Studio</span>\n    </h1>\n    <div class="model-card-content">\n        <div class="model-card-item">\n            <strong>Models:</strong>\n            <a href="https://huggingface.co/pnnbao-ump/VieNeu-TTS" target="_blank" class="model-card-link">VieNeu-TTS</a>\n            <span>•</span>\n            <a href="https://huggingface.co/pnnbao-ump/VieNeu-TTS-q4-gguf" target="_blank" class="model-card-link">Q4-GGUF</a>\n            <span>•</span>\n            <a href="https://huggingface.co/pnnbao-ump/VieNeu-TTS-q8-gguf" target="_blank" class="model-card-link">Q8-GGUF</a>\n        </div>\n        <div class="model-card-item">\n            <strong>Repository:</strong>\n            <a href="https://github.com/pnnbao97/VieNeu-TTS" target="_blank" class="model-card-link">GitHub</a>\n        </div>\n        <div class="model-card-item">\n            <strong>Tác giả:</strong>\n            <span>Phạm Nguyễn Ngọc Bảo</span>\n        </div>\n    </div>\n</div>\n        ')
        with gr.Group():
            with gr.Row():
                backbone_select = gr.Dropdown(list(BACKBONE_CONFIGS.keys()), value='VieNeu-TTS (GPU)', label='🦜 Backbone')
                codec_select = gr.Dropdown(list(CODEC_CONFIGS.keys()), value='NeuCodec (Standard)', label='🎵 Codec')
                device_choice = gr.Radio(['Auto', 'CPU', 'CUDA'], value='Auto', label='🖥️ Device')
            with gr.Row():
                enable_triton = gr.Checkbox(value=True, label='⚡ Enable Triton Compilation')
                max_batch_size = gr.Slider(minimum=1, maximum=16, value=8, step=1, label='📊 Max Batch Size', info='Giảm nếu gặp lỗi OOM. 4-6 cho GPU 8GB, 8-12 cho GPU 16GB+')
            gr.Markdown('⚠️ **Lưu ý:** Nếu máy bạn chỉ có CPU vui lòng chọn phiên bản GGUF (Q4/Q8) để có tốc độ nhanh nhất.\n\n💡 **Max Batch Size:** Số lượng đoạn văn bản được xử lý cùng lúc. Giá trị cao = nhanh hơn nhưng tốn VRAM hơn. Giảm xuống nếu gặp lỗi "Out of Memory".')
            btn_load = gr.Button('🔄 Tải Model', variant='primary')
            model_status = gr.Markdown('⏳ Chưa tải model.')
        with gr.Row(elem_classes='container'):
            with gr.Column(scale=3):
                text_input = gr.Textbox(label=f'Văn bản (Streaming hỗ trợ tới {MAX_TOTAL_CHARS_STREAMING} ký tự, chia chunk {MAX_CHARS_PER_CHUNK} ký tự)', lines=4, value='Hà Nội, trái tim của Việt Nam, là một thành phố ngàn năm văn hiến với bề dày lịch sử và văn hóa độc đáo. Bước chân trên những con phố cổ kính quanh Hồ Hoàn Kiếm, du khách như được du hành ngược thời gian, chiêm ngưỡng kiến trúc Pháp cổ điển hòa quyện với nét kiến trúc truyền thống Việt Nam. Mỗi con phố trong khu phố cổ mang một tên gọi đặc trưng, phản ánh nghề thủ công truyền thống từng thịnh hành nơi đây như phố Hàng Bạc, Hàng Đào, Hàng Mã. Ẩm thực Hà Nội cũng là một điểm nhấn đặc biệt, từ tô phở nóng hổi buổi sáng, bún chả thơm lừng trưa hè, đến chè Thái ngọt ngào chiều thu. Những món ăn dân dã này đã trở thành biểu tượng của văn hóa ẩm thực Việt, được cả thế giới yêu mến. Người Hà Nội nổi tiếng với tính cách hiền hòa, lịch thiệp nhưng cũng rất cầu toàn trong từng chi tiết nhỏ, từ cách pha trà sen cho đến cách chọn hoa sen tây để thưởng trà.')
                with gr.Tabs() as tabs:
                    with gr.TabItem('👤 Preset', id='preset_mode') as tab_preset:
                        initial_voices = get_voice_options('VieNeu-TTS (GPU)')
                        default_voice = initial_voices[0] if initial_voices else None
                        voice_select = gr.Dropdown(initial_voices, value=default_voice, label='Giọng mẫu')
                    with gr.TabItem('🦜 Voice Cloning', id='custom_mode') as tab_custom:
                        custom_audio = gr.Audio(label='Audio giọng mẫu (10-15 giây) (.wav)', type='filepath')
                        custom_text = gr.Textbox(label='Nội dung audio mẫu - vui lòng gõ đúng nội dung của audio mẫu - kể cả dấu câu vì model rất nhạy cảm với dấu câu (.,?!)')
                    with gr.TabItem('🎙️ Batch Preview', id='batch_preview') as tab_batch:
                        gr.Markdown('### 🎧 Nghe thử tất cả các giọng mẫu')
                        with gr.Row():
                            btn_batch_generate = gr.Button('🚀 Tạo tất cả Demo (Preview)', variant='primary')
                        batch_audio_outputs = []
                        with gr.Row():
                            for i, v_name in enumerate(GGUF_ALLOWED_VOICES[:4]):
                                with gr.Column():
                                    gr.Markdown(f'**{v_name}**')
                                    audio_v = gr.Audio(label=None, type='filepath', show_label=False)
                                    batch_audio_outputs.append(audio_v)
                        with gr.Row():
                            for i, v_name in enumerate(GGUF_ALLOWED_VOICES[4:8]):
                                with gr.Column():
                                    gr.Markdown(f'**{v_name}**')
                                    audio_v = gr.Audio(label=None, type='filepath', show_label=False)
                                    batch_audio_outputs.append(audio_v)
                generation_mode = gr.Radio(['Standard (Một lần)'], value='Standard (Một lần)', label='Chế độ sinh')
                use_batch = gr.Checkbox(value=True, label='⚡ Batch Processing', info='Xử lý nhiều đoạn cùng lúc (chỉ áp dụng khi sử dụng GPU và đã cài đặt LMDeploy)')
                current_mode_state = gr.State('preset_mode')
                btn_generate = gr.Button('🎵 Bắt đầu', variant='primary', size='lg', interactive=False)
            with gr.Column(scale=2):
                audio_output = gr.Audio(label='Kết quả', type='filepath', autoplay=True)
                status_output = gr.Textbox(label='Trạng thái', elem_classes='status-box')

        def update_info(backbone: str) -> str:
            return f"Streaming: {('✅' if BACKBONE_CONFIGS[backbone]['supports_streaming'] else '❌')}"
        backbone_select.change(update_info, backbone_select, model_status)
        backbone_select.change(update_voice_dropdown, [backbone_select, voice_select], voice_select)
        tab_preset.select(lambda: 'preset_mode', outputs=current_mode_state)
        tab_custom.select(lambda: 'custom_mode', outputs=current_mode_state)
        btn_load.click(fn=load_model, inputs=[backbone_select, codec_select, device_choice, enable_triton, max_batch_size], outputs=[model_status, btn_generate, btn_load])
        btn_batch_generate.click(fn=batch_synthesize, inputs=[text_input], outputs=batch_audio_outputs)
        btn_generate.click(fn=synthesize_speech, inputs=[text_input, voice_select, custom_audio, custom_text, current_mode_state, generation_mode, use_batch], outputs=[audio_output, status_output])
if __name__ == '__main__':
    server_name = os.getenv('GRADIO_SERVER_NAME', '127.0.0.1')
    server_port = int(os.getenv('GRADIO_SERVER_PORT', '7860'))
    demo.queue().launch(server_name=server_name, server_port=server_port)