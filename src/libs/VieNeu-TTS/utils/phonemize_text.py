import os
import json
import platform
import glob
from phonemizer import phonemize
from phonemizer.backend.espeak.espeak import EspeakWrapper
from utils.normalize_text import VietnameseTTSNormalizer
PHONEME_DICT_PATH = os.getenv('PHONEME_DICT_PATH', os.path.join(os.path.dirname(__file__), 'phoneme_dict.json'))

def load_phoneme_dict(path=PHONEME_DICT_PATH):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f'Phoneme dictionary not found at {path}. Please create it or set PHONEME_DICT_PATH environment variable.')

def setup_espeak_library():
    system = platform.system()
    if system == 'Windows':
        _setup_windows_espeak()
    elif system == 'Linux':
        _setup_linux_espeak()
    elif system == 'Darwin':
        _setup_macos_espeak()
    else:
        raise OSError(f'Unsupported OS: {system}. Only Windows, Linux, and macOS are supported.')

def _setup_windows_espeak():
    default_path = 'C:\\Program Files\\eSpeak NG\\libespeak-ng.dll'
    if os.path.exists(default_path):
        EspeakWrapper.set_library(default_path)
    else:
        raise FileNotFoundError(f'eSpeak library not found at {default_path}. Please install eSpeak NG from: https://github.com/espeak-ng/espeak-ng/releases')

def _setup_linux_espeak():
    search_patterns = ['/usr/lib/x86_64-linux-gnu/libespeak-ng.so*', '/usr/lib/x86_64-linux-gnu/libespeak.so*', '/usr/lib/libespeak-ng.so*', '/usr/lib64/libespeak-ng.so*', '/usr/local/lib/libespeak-ng.so*', '/usr/lib/aarch64-linux-gnu/libespeak-ng.so*']
    for pattern in search_patterns:
        matches = glob.glob(pattern)
        if matches:
            EspeakWrapper.set_library(sorted(matches, key=len)[0])
            return
    direct_paths = ['/usr/lib/aarch64-linux-gnu/libespeak-ng.so.1', '/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1']
    for path in direct_paths:
        if os.path.exists(path):
            EspeakWrapper.set_library(path)
            return
    raise RuntimeError('eSpeak NG library not found. Install with:\n  Ubuntu/Debian: sudo apt-get install espeak-ng\n  Fedora: sudo dnf install espeak-ng\n  Arch: sudo pacman -S espeak-ng\nSee: https://github.com/pnnbao97/VieNeu-TTS/issues/5')

def _setup_macos_espeak():
    espeak_lib = os.environ.get('PHONEMIZER_ESPEAK_LIBRARY')
    paths_to_check = [espeak_lib, '/opt/homebrew/lib/libespeak-ng.dylib', '/usr/local/lib/libespeak-ng.dylib', '/opt/local/lib/libespeak-ng.dylib']
    for path in paths_to_check:
        if path and os.path.exists(path):
            EspeakWrapper.set_library(path)
            return
    raise FileNotFoundError('eSpeak library not found. Install with:\n  brew install espeak-ng\nOr set: export PHONEMIZER_ESPEAK_LIBRARY=/path/to/libespeak-ng.dylib')
try:
    setup_espeak_library()
    phoneme_dict = load_phoneme_dict()
    normalizer = VietnameseTTSNormalizer()
except Exception as e:
    print(f'Initialization error: {e}')
    raise

def phonemize_text(text: str) -> str:
    text = normalizer.normalize(text)
    return phonemize(text, language='vi', backend='espeak', preserve_punctuation=True, with_stress=True, language_switch='remove-flags')

def phonemize_with_dict(text: str, phoneme_dict=phoneme_dict) -> str:
    text = normalizer.normalize(text)
    words = text.split()
    result = []
    for word in words:
        if word in phoneme_dict:
            phone_word = phoneme_dict[word]
        else:
            try:
                phone_word = phonemize(word, language='vi', backend='espeak', preserve_punctuation=True, with_stress=True, language_switch='remove-flags')
                if word.lower().startswith('r'):
                    phone_word = 'ɹ' + phone_word[1:]
                phoneme_dict[word] = phone_word
            except Exception as e:
                print(f"Warning: Could not phonemize '{word}': {e}")
                phone_word = word
        result.append(phone_word)
    return ' '.join(result)