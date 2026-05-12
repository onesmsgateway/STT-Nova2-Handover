import os
import subprocess
import shlex
import wave
import numpy as np

def _file_cmd_info(file_path: str):
    try:
        out = subprocess.check_output(f'file -b {shlex.quote(file_path)}', shell=True, text=True).strip()
        return out
    except Exception:
        return None

def analyze_audio(file_path):
    result = {'exists': os.path.exists(file_path), 'codec': None, 'channels': None, 'sample_rate_hz': None, 'duration_sec': None, 'rms_overall': None, 'silence_ratio': None, 'file_cmd': None, 'warnings': [], 'ok': False}
    if not result['exists']:
        result['warnings'].append('File không tồn tại')
        return result
    result['file_cmd'] = _file_cmd_info(file_path)
    if result['file_cmd']:
        lower = result['file_cmd'].lower()
        if 'gsm' in lower:
            result['codec'] = 'GSM 6.10'
        if 'mono' in lower:
            result['channels'] = 1
        elif 'stereo' in lower:
            result['channels'] = 2
        for token in lower.replace(',', ' ').split():
            if token.endswith('hz') and token[:-2].isdigit():
                try:
                    result['sample_rate_hz'] = int(token[:-2])
                except Exception:
                    pass
    try:
        with wave.open(file_path, 'rb') as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / frame_rate if frame_rate else 0.0
            result['channels'] = result['channels'] or channels
            result['sample_rate_hz'] = result['sample_rate_hz'] or frame_rate
            result['duration_sec'] = result['duration_sec'] or duration
            if result['codec'] is None:
                result['codec'] = 'PCM'
            frames = wf.readframes(n_frames)
        if sample_width == 1:
            arr = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
            arr = (arr - 128.0) / 128.0
        elif sample_width == 2:
            arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            arr = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
        if result['channels'] and result['channels'] > 1:
            try:
                arr = arr.reshape(-1, result['channels']).mean(axis=1)
            except Exception:
                pass
        rms = float(np.sqrt(np.mean(arr ** 2))) if arr.size else None
        result['rms_overall'] = rms
        thr = 0.01
        result['silence_ratio'] = float(np.mean(np.abs(arr) < thr)) if arr.size else None
        if (result['sample_rate_hz'] or 0) <= 8000:
            result['warnings'].append('Sample rate thấp (<= 8000 Hz)')
        if result['channels'] == 1:
            result['warnings'].append('Mono channel')
        if result['codec'] == 'GSM 6.10':
            result['warnings'].append('Codec GSM 6.10 (nén mạnh)')
        if (result['silence_ratio'] or 0) > 0.9:
            result['warnings'].append('Tỷ lệ im lặng rất cao (> 90%)')
        if (result['rms_overall'] or 0) < 0.003:
            result['warnings'].append('Âm lượng (RMS) rất thấp')
        ok = True
        if not result['exists']:
            ok = False
        if result['sample_rate_hz'] is not None and result['sample_rate_hz'] < 8000:
            ok = False
        if result['silence_ratio'] is not None and result['silence_ratio'] >= 0.999:
            ok = False
        if result['rms_overall'] is not None and result['rms_overall'] < 0.001:
            ok = False
        result['ok'] = ok
        return result
    except Exception as e:
        result['warnings'].append(f'Lỗi khi phân tích audio: {e}')
        return result