import os
import asyncio
import re
import numpy as np
import hashlib
import shutil
from typing import Dict, Any, List
from src.core.logger import setup_logger
from src.interfaces.tts import TTSProvider, VoiceCloningProvider
from src.core.config import OPENAI_API_KEY
logger = setup_logger(__name__)

class OpenAITTSProvider(TTSProvider):

    async def synthesize(self, text: str, output_path: str, options: Dict[str, Any]=None) -> bool:
        try:
            from openai import OpenAI
            if not OPENAI_API_KEY:
                logger.error('OpenAI API Key not found')
                return False
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.audio.speech.create(model='tts-1', voice='alloy', input=text)
            response.stream_to_file(output_path)
            return True
        except ImportError:
            logger.error('Vui lòng cài đặt thư viện openai: pip install openai')
            return False
        except Exception as e:
            logger.error(f'OpenAI TTS error: {e}')
            return False

class CoquiTTSProvider(TTSProvider, VoiceCloningProvider):

    def __init__(self):
        self.model = None
        self.current_model_id = None
        self.device = 'cpu'

    async def synthesize(self, text: str, output_path: str, options: Dict[str, Any]=None) -> bool:
        try:
            language = options.get('language', 'vi')
            print(f'DEBUG: synthesize called with language={language}, model={type(self.model)}')
            target_model = 'vixtts' if language == 'vi' else 'xtts_v2'
            self._load_model(target_model)
            speaker_wav = options.get('speaker_wav')
            if not speaker_wav:
                logger.warning('XTTS requires a speaker_wav reference. Using default.')
                default_wav = '/app/resource/models/vixtts/samples/nu-nhe-nhang.wav'
                if os.path.exists(default_wav):
                    speaker_wav = default_wav
                else:
                    logger.error(f'Default speaker file not found at: {default_wav}')
                    return False
            from TTS.utils.synthesizer import Synthesizer
            if isinstance(self.model, Synthesizer):
                wav = await asyncio.to_thread(self.model.tts, text=text, speaker_name=None, speaker_wav=speaker_wav, language_name=language)
                self.model.save_wav(wav, output_path)
            else:
                kwargs = {'text': text, 'file_path': output_path, 'speaker_wav': speaker_wav, 'language': language}
                await asyncio.to_thread(self.model.tts_to_file, **kwargs)
            return True
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f'Coqui TTS error: {e}')
            return False

    def _load_model(self, model_id='xtts_v2'):
        if self.model and self.current_model_id == model_id:
            return
        try:
            import torch
            from TTS.api import TTS
            from TTS.utils.synthesizer import Synthesizer
            self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
            use_cuda = self.device == 'cuda'
            logger.info(f"Loading Coqui TTS model '{model_id}' on {self.device}...")
            if model_id == 'vixtts':
                model_dir = '/app/resource/models/vixtts'
                config_path = os.path.join(model_dir, 'config.json')
                vocab_path = os.path.join(model_dir, 'vocab.json')
                checkpoint_path = None
                for f in os.listdir(model_dir):
                    if f.endswith('.pth') or f.endswith('.bin'):
                        checkpoint_path = os.path.join(model_dir, f)
                        break
                if not checkpoint_path:
                    raise FileNotFoundError('Could not find model checkpoint in vixtts dir')
                speakers_file = os.path.join(model_dir, 'speakers_xtts.pth')
                logger.info(f'Loading checkpoint from dir: {model_dir}')
                logger.info(f'Using speakers file: {speakers_file}')
                self.model = Synthesizer(tts_checkpoint='', tts_config_path=config_path, tts_speakers_file=speakers_file, model_dir=model_dir, use_cuda=use_cuda)
                logger.info(f'Speaker Manager: {self.model.tts_model.speaker_manager}')
                logger.info(f'Language Manager: {self.model.tts_model.language_manager}')
                try:
                    from TTS.tts.layers.xtts.tokenizer import VoiceBpeTokenizer
                    if not hasattr(VoiceBpeTokenizer, '_original_preprocess_text'):
                        logger.info("Applying monkeypatch to VoiceBpeTokenizer.preprocess_text for 'vi' support")
                        VoiceBpeTokenizer._original_preprocess_text = VoiceBpeTokenizer.preprocess_text

                        def patched_preprocess_text(self, txt, lang=None):
                            if lang == 'vi':
                                lang = 'en'
                            return VoiceBpeTokenizer._original_preprocess_text(self, txt, lang)
                        VoiceBpeTokenizer.preprocess_text = patched_preprocess_text
                    tokenizer = self.model.tts_model.tokenizer
                    if 'vi' not in tokenizer.char_limits:
                        logger.info("Injecting 'vi' into char_limits")
                        tokenizer.char_limits['vi'] = 250
                except Exception as ex:
                    logger.warning(f'Could not patch tokenizer: {ex}')
            else:
                self.model = TTS('tts_models/multilingual/multi-dataset/xtts_v2').to(self.device)
            self.current_model_id = model_id
            logger.info(f'✅ Coqui {model_id} loaded')
        except ImportError:
            logger.error("❌ Thư viện 'TTS' chưa được cài đặt. Chạy: pip install TTS")
            raise Exception('Coqui TTS library missing')
        except Exception as e:
            logger.error(f'❌ Error loading Coqui TTS: {e}')
            raise

    async def clone_voice(self, reference_audio_path: str, text: str, output_path: str) -> bool:
        try:
            return await self.synthesize(text, output_path, {'speaker_wav': reference_audio_path, 'language': 'vi'})
        except Exception as e:
            return False

class VieNeuTTSProvider(TTSProvider):

    def __init__(self):
        super().__init__()
        self.model = None
        self.voices = {}
        self._load_model()

    def _load_model(self):
        try:
            import sys
            import os
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            lib_path = os.path.abspath(os.path.join(current_file_dir, '..', '..', 'libs', 'VieNeu-TTS'))
            if os.path.exists(lib_path) and lib_path not in sys.path:
                sys.path.append(lib_path)
                logger.info(f'Added {lib_path} to sys.path')
            neucodec_path = os.path.abspath(os.path.join(current_file_dir, '..', '..', 'libs', 'neucodec'))
            if os.path.exists(neucodec_path) and neucodec_path not in sys.path:
                sys.path.append(neucodec_path)
                logger.info(f'Added {neucodec_path} to sys.path')
            try:
                from vieneu_tts import VieNeuTTS
            except ImportError:
                if os.path.exists(os.path.join(lib_path, 'vieneu_tts', 'vieneu_tts.py')):
                    sys.path.append(os.path.join(lib_path))
                    from vieneu_tts import VieNeuTTS
                else:
                    raise
            base_model_dir = os.path.join(os.getcwd(), 'resource', 'models', 'vieneu')
            backbone_path = os.path.join(base_model_dir, 'backbone')
            codec_path = os.path.join(base_model_dir, 'codec')
            if not os.path.exists(backbone_path) or not os.path.exists(codec_path):
                logger.warning('Local VieNeu-TTS models not found. Using default Repo IDs (requires internet).')
                backbone_repo = 'pnnbao-ump/VieNeu-TTS-q4-gguf'
                codec_repo = 'neuphonic/neucodec'
            else:
                backbone_repo = backbone_path
                codec_repo = codec_path
                if os.path.isdir(backbone_repo):
                    import glob
                    gguf_files = glob.glob(os.path.join(backbone_path, '*.gguf'))
                    if gguf_files:
                        backbone_repo = gguf_files[0]
                        logger.info(f'Resolved GGUF backbone file: {backbone_repo}')
                    else:
                        logger.warning(f'No .gguf file found in {backbone_path}. Model loading might fail if using quantized backend.')
            logger.info(f'Loading VieNeu-TTS from: {backbone_repo} / {codec_repo}')
            self.model = VieNeuTTS(backbone_repo=backbone_repo, backbone_device='cpu', codec_repo=codec_repo, codec_device='cpu')
            sample_dir = os.path.join(lib_path, 'sample')
            logger.info(f'🔎 Scanning for voices in: {sample_dir}')
            if os.path.exists(sample_dir):
                try:
                    all_files = os.listdir(sample_dir)
                    logger.info(f'📁 Directory exists. Contents ({len(all_files)} files): {all_files[:10]}...')
                except Exception as e:
                    logger.error(f'❌ Failed to list dir {sample_dir}: {e}')
                import glob
                import torch
                wav_files = glob.glob(os.path.join(sample_dir, '*.wav'))
                logger.info(f'🎵 Found {len(wav_files)} .wav files via glob')
                for wav_path in wav_files:
                    voice_name = os.path.basename(wav_path).replace('.wav', '')
                    txt_path = wav_path.replace('.wav', '.txt')
                    pt_path = wav_path.replace('.wav', '.pt')
                    if os.path.exists(txt_path):
                        try:
                            with open(txt_path, 'r', encoding='utf-8') as f:
                                ref_text = f.read().strip()
                            if os.path.exists(pt_path):
                                logger.info(f'Loading pre-calculated codes for {voice_name} from .pt file')
                                ref_codes = torch.load(pt_path, map_location='cpu')
                                if isinstance(ref_codes, torch.Tensor):
                                    ref_codes = ref_codes.tolist()
                            else:
                                logger.info(f'Encoding reference for {voice_name} from .wav file')
                                ref_codes = self.model.encode_reference(wav_path)
                            self.voices[voice_name] = {'codes': ref_codes, 'text': ref_text}
                            logger.info(f'Loaded preset voice: {voice_name}')
                        except Exception as ve:
                            logger.error(f'Error loading voice {voice_name}: {ve}')
            if 'Ngọc (nữ miền Bắc)' in self.voices:
                self.default_voice = 'Ngọc (nữ miền Bắc)'
            elif self.voices:
                self.default_voice = list(self.voices.keys())[0]
            else:
                self.default_voice = None
            logger.info('✅ VieNeu-TTS Provider loaded successfully')
        except Exception as e:
            import traceback
            import sys
            print(f'CRITICAL ERROR LOADING VIENEU-TTS: {e}', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            logger.error(f'Failed to load VieNeu-TTS: {e}')
            self.model = None

    def _split_into_sentences(self, text: str) -> List[str]:
        sentences = re.split('(?<=[.!?])\\s+|\\n+', text)
        return [s.strip() for s in sentences if s.strip()]

    async def synthesize(self, text: str, output_path: str, options: dict=None) -> bool:
        if not self.model:
            logger.error('VieNeu-TTS model not loaded')
            return False
        try:
            import soundfile as sf
            import asyncio
            import numpy as np
            voice_name = options.get('voice') if options else None
            if voice_name and voice_name in self.voices:
                ref_codes = self.voices[voice_name]['codes']
                ref_text = self.voices[voice_name]['text']
            elif self.default_voice and self.default_voice in self.voices:
                ref_codes = self.voices[self.default_voice]['codes']
                ref_text = self.voices[self.default_voice]['text']
                voice_name = self.default_voice
            else:
                logger.error('No speaker available for synthesis')
                return False
            MAX_REF_TOKENS = 512
            if len(ref_codes) > MAX_REF_TOKENS:
                logger.info(f"⚠️ Truncating reference codes for '{voice_name}' from {len(ref_codes)} to {MAX_REF_TOKENS} for stability")
                ref_codes = ref_codes[:MAX_REF_TOKENS]
            else:
                logger.info(f"🎤 Using full reference for '{voice_name}' ({len(ref_codes)} tokens)")
            rate_str = options.get('rate', '+0%') if options else '+0%'
            cache_dir = 'static/cache/tts_vieneu'
            os.makedirs(cache_dir, exist_ok=True)
            cache_key = hashlib.md5(f'{voice_name}_{text}_{rate_str}'.encode()).hexdigest()
            cache_path = os.path.join(cache_dir, f'{cache_key}.wav')
            if os.path.exists(cache_path):
                logger.info(f"💾 Cache hit for voice '{voice_name}' and text. Serving from {cache_path}")
                shutil.copy2(cache_path, output_path)
                return True
            chunks = self._split_into_sentences(text)
            if not chunks:
                return False
            speed = 1.0
            rate_str = options.get('rate', '+0%') if options else '+0%'
            try:
                if isinstance(rate_str, str) and (rate_str.startswith('+') or rate_str.startswith('-')):
                    val = int(rate_str.strip('%')) / 100.0
                    speed = 1.0 + val
            except:
                pass
            logger.info(f'Synthesizing {len(chunks)} chunks with VieNeu-TTS (speed={speed})...')
            loop = asyncio.get_running_loop()
            all_wavs = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing chunk {i + 1}/{len(chunks)}: '{chunk[:30]}...'")
                wav = None
                for attempt in range(3):
                    try:
                        logger.info(f'Inference attempt {attempt + 1} for chunk {i + 1}...')
                        wav = await loop.run_in_executor(None, lambda c=chunk: self.model.infer(c, ref_codes, ref_text))
                        if wav is not None:
                            break
                    except Exception as ie:
                        logger.warning(f'Inference attempt {attempt + 1} failed: {ie}')
                        if attempt == 2:
                            raise ie
                        await asyncio.sleep(1)
                if speed != 1.0:
                    try:
                        import librosa
                        wav = librosa.effects.time_stretch(wav, rate=speed)
                    except Exception as le:
                        logger.warning(f'Failed to apply time_stretch: {le}')
                all_wavs.append(wav)
            final_wav = np.concatenate(all_wavs)
            import soundfile as sf
            await loop.run_in_executor(None, sf.write, output_path, final_wav, 24000)
            shutil.copy2(output_path, cache_path)
            logger.info(f'✅ VieNeu-TTS synthesized successfully: {output_path} (Saved to cache)')
            return True
        except Exception as e:
            logger.error(f'VieNeu-TTS synthesis error: {e}')
            import traceback
            traceback.print_exc()
            return False

    async def clone_voice(self, reference_path: str, text: str, output_path: str, ref_text: str=None, options: dict=None) -> bool:
        if not self.model:
            logger.error('VieNeu-TTS model not loaded')
            return False
        try:
            import soundfile as sf
            import asyncio
            import numpy as np
            if not ref_text:
                logger.warning("VieNeu-TTS requires 'ref_text'. Proceeding with placeholder.")
                ref_text = 'Xin chào'
            chunks = self._split_into_sentences(text)
            if not chunks:
                return False
            logger.info(f'Cloning voice for {len(chunks)} chunks from {os.path.basename(reference_path)}')
            loop = asyncio.get_running_loop()
            speed = 1.0
            rate_str = options.get('rate', '+0%') if options else '+0%'
            try:
                if isinstance(rate_str, str) and (rate_str.startswith('+') or rate_str.startswith('-')):
                    val = int(rate_str.strip('%')) / 100.0
                    speed = 1.0 + val
            except:
                pass
            ref_codes = await loop.run_in_executor(None, self.model.encode_reference, reference_path)
            speed = 1.0
            all_wavs = []
            for i, chunk in enumerate(chunks):
                logger.info(f"Processing clone chunk {i + 1}/{len(chunks)}: '{chunk[:30]}...'")
                wav = None
                for attempt in range(3):
                    try:
                        logger.info(f'Clone inference attempt {attempt + 1} for chunk {i + 1}...')
                        wav = await loop.run_in_executor(None, lambda c=chunk: self.model.infer(c, ref_codes, ref_text))
                        if wav is not None:
                            break
                    except Exception as ie:
                        logger.warning(f'Clone attempt {attempt + 1} failed: {ie}')
                        if attempt == 2:
                            raise ie
                        await asyncio.sleep(1)
                if speed != 1.0:
                    try:
                        import librosa
                        wav = librosa.effects.time_stretch(wav, rate=speed)
                    except Exception as le:
                        logger.warning(f'Failed to apply time_stretch in clone: {le}')
                all_wavs.append(wav)
            final_wav = np.concatenate(all_wavs)
            await loop.run_in_executor(None, sf.write, output_path, final_wav, 24000)
            return True
        except Exception as e:
            logger.error(f'VieNeu-TTS cloning error: {e}')
            return False

class ValtecTTSProvider(TTSProvider):

    def __init__(self):
        self.engine = None

    def _load_engine(self):
        try:
            from valtec_tts import TTS
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.engine = TTS(device=device)
            logger.info(f'✅ Valtec TTS loaded on {device}')
        except ImportError:
            logger.error('Valtec TTS not installed. Please install: pip install git+https://github.com/tronghieuit/valtec-tts.git')
        except Exception as e:
            logger.error(f'Failed to load Valtec TTS: {e}')

    async def synthesize(self, text: str, output_path: str, options: Dict[str, Any]=None) -> bool:
        if not self.engine:
            self._load_engine()
            if not self.engine:
                return False
        try:
            options = options or {}
            speaker = options.get('speaker', 'female')
            speed = options.get('speed', 1.0)
            await asyncio.to_thread(self.engine.speak, text, output_path=output_path, speaker=speaker, speed=speed)
            return True
        except Exception as e:
            logger.error(f'Valtec TTS error: {e}')
            return False

class EdgeTTSProvider(TTSProvider):

    def __init__(self):
        self.default_voice = 'vi-VN-HoaiMyNeural'

    async def synthesize(self, text: str, output_path: str, options: Dict[str, Any]=None) -> bool:
        try:
            import edge_tts
            options = options or {}
            voice = options.get('voice', self.default_voice)
            rate = options.get('rate', '+0%')
            volume = options.get('volume', '+0%')
            communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
            await communicate.save(output_path)
            logger.info(f'✅ Edge TTS synthesized successfully: {output_path}')
            return True
        except ImportError:
            logger.error('Vui lòng cài đặt thư viện edge-tts: pip install edge-tts')
            return False
        except Exception as e:
            logger.error(f'Edge TTS error: {e}')
            return False