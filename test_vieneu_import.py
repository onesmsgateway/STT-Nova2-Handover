import os
import sys
lib_path = os.path.abspath('src/libs/VieNeu-TTS')
if lib_path not in sys.path:
    sys.path.append(lib_path)
try:
    print('Trying to import VieNeuTTS...')
    from vieneu_tts import VieNeuTTS
    print('Success!')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()