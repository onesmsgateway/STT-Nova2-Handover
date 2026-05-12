import asyncio
import os
import sys
import logging
import psutil
import time
from pathlib import Path
from config import DEEPGRAM_API_KEY, GOOGLE_API_KEY, MAX_WORDS, GOOGLE_API_KEYS, GOOGLE_CLASSIFICATION_API_KEYS, DEEPGRAM_API_KEYS, DEBUG_MODE, AUDIO_PROCESSING_MODE, ENGINE, DISABLE_TRIM, MIN_DURATION_THRESHOLD
logger = logging.getLogger(__name__)
from audio_analyze import analyze_audio as analyze_audio_file
from audio_enhanced import process_audio_comprehensive
from stt_service import transcribe_prerecorded
from summarizer import summarize_transcript, summarize_with_google_ai, get_summary_method
from text_classifier import classify_conversation_content, GoogleAPIKeyManager as ClassifierKeyManager

class AudioProcessor:

    def __init__(self, deepgram_api_key, google_api_key=None, audio_processing_mode=None, max_words=None):
        self.deepgram_api_key = deepgram_api_key
        self.google_api_key = google_api_key
        self.audio_processing_mode = audio_processing_mode or AUDIO_PROCESSING_MODE
        self.max_words = max_words or MAX_WORDS
        self.engine = ENGINE
        from summarizer import GoogleAPIKeyManager
        self.google_key_manager = GoogleAPIKeyManager(GOOGLE_API_KEYS) if GOOGLE_API_KEYS else None
        self.classifier_key_manager = ClassifierKeyManager(GOOGLE_CLASSIFICATION_API_KEYS) if GOOGLE_CLASSIFICATION_API_KEYS else None
        from stt_service import DeepgramAPIKeyManager
        self.deepgram_key_manager = DeepgramAPIKeyManager(DEEPGRAM_API_KEYS) if DEEPGRAM_API_KEYS else None
        self.processed_files = []
        self.audio_processing_info = {'normalization': False, 'noise_reduction': False, 'enhance_quality': False, 'silence_removal': False, 'compression': False, 'de_essing': False, 'de_reverb': False, 'processing_applied': False}
        self.cpu_threshold = 85.0
        self.ram_threshold = 85.0
        self.telegram_bot = None

    def set_telegram_bot(self, telegram_bot):
        self.telegram_bot = telegram_bot

    def get_cpu_percent(self) -> float:
        try:
            return psutil.cpu_percent(interval=0.1)
        except Exception as e:
            logger.error(f'❌ Lỗi khi lấy CPU percent: {e}')
            return 0.0

    def get_memory_percent(self) -> float:
        try:
            return psutil.virtual_memory().percent
        except Exception as e:
            logger.error(f'❌ Lỗi khi lấy Memory percent: {e}')
            return 0.0

    async def _run_phowhisper_with_monitoring(self, audio_path: str, audio_url: str):
        import subprocess
        import threading
        import queue
        try:
            logger.info('🚀 Bắt đầu PhoWhisper với CPU monitoring...')
            result_queue = queue.Queue()
            cpu_monitor_queue = queue.Queue()
            monitoring_active = threading.Event()
            monitoring_active.set()

            def run_phowhisper():
                try:
                    from phowhisper_engine import transcribe as pw_transcribe
                    logger.info('🎯 PhoWhisper process started...')
                    pw_result = pw_transcribe(audio_path)
                    result_queue.put(('success', pw_result))
                except Exception as e:
                    logger.error(f'❌ PhoWhisper process error: {e}')
                    result_queue.put(('error', str(e)))

            def monitor_cpu():
                consecutive_high_cpu = 0
                grace_period = 5.0
                grace_start = None
                while monitoring_active.is_set():
                    try:
                        cpu_percent = self.get_cpu_percent()
                        memory_percent = self.get_memory_percent()
                        cpu_high = cpu_percent > self.cpu_threshold
                        ram_high = memory_percent > self.ram_threshold
                        resource_high = cpu_high or ram_high
                        if resource_high:
                            consecutive_high_cpu += 1
                            if consecutive_high_cpu == 1:
                                grace_start = time.time()
                                resource_type = []
                                if cpu_high:
                                    resource_type.append(f'CPU: {cpu_percent:.1f}% (threshold: {self.cpu_threshold}%)')
                                if ram_high:
                                    resource_type.append(f'RAM: {memory_percent:.1f}% (threshold: {self.ram_threshold}%)')
                                resource_msg = ' + '.join(resource_type)
                                logger.warning(f'⚠️ Resource cao: {resource_msg}')
                                logger.warning(f'   Grace period: {grace_period}s')
                                if self.telegram_bot:
                                    try:
                                        resource_details = []
                                        if cpu_high:
                                            resource_details.append(f'• CPU: {cpu_percent:.1f}% (threshold: {self.cpu_threshold}%)')
                                        if ram_high:
                                            resource_details.append(f'• RAM: {memory_percent:.1f}% (threshold: {self.ram_threshold}%)')
                                        resource_details_str = '\n'.join(resource_details)
                                        message = f"\n🚨 **RESOURCE QUÁ CAO - PHOWHISPER ĐANG CHẠY**\n\n📊 **Thông tin hệ thống:**\n{resource_details_str}\n\n🎵 **Audio đang xử lý:**\n`{audio_url}`\n\n⏰ **Thời gian:** {time.strftime('%H:%M:%S %d/%m/%Y')}\n\n⚠️ **Hệ thống sẽ tự động cancel sau {grace_period}s nếu resource vẫn cao**\n\n🤖 **Tùy chọn:**\n• Reply 'YES' để chuyển sang Deepgram ngay\n• Reply 'NO' để từ chối và bỏ qua audio này\n• Timeout: 30 giây\n"
                                        try:
                                            loop = asyncio.get_event_loop()
                                            if loop.is_running():
                                                asyncio.create_task(self.telegram_bot.send_message(chat_id=self.telegram_bot.admin_chat_id, text=message, parse_mode='Markdown'))
                                            else:
                                                asyncio.run(self.telegram_bot.send_message(chat_id=self.telegram_bot.admin_chat_id, text=message, parse_mode='Markdown'))
                                        except RuntimeError:
                                            import threading

                                            def send_telegram():
                                                try:
                                                    asyncio.run(self.telegram_bot.send_message(chat_id=self.telegram_bot.admin_chat_id, text=message, parse_mode='Markdown'))
                                                except Exception as e:
                                                    logger.error(f'❌ Lỗi khi gửi Telegram trong thread: {e}')
                                            thread = threading.Thread(target=send_telegram, daemon=True)
                                            thread.start()
                                        logger.info(f'📱 Đã gửi CPU high alert cho {audio_url}')
                                    except Exception as e:
                                        logger.error(f'❌ Lỗi khi gửi Telegram notification: {e}')
                            elif consecutive_high_cpu > 1:
                                if grace_start and time.time() - grace_start >= grace_period:
                                    resource_type = []
                                    if cpu_high:
                                        resource_type.append(f'CPU: {cpu_percent:.1f}%')
                                    if ram_high:
                                        resource_type.append(f'RAM: {memory_percent:.1f}%')
                                    resource_msg = ' + '.join(resource_type)
                                    logger.error(f'🚨 Resource quá cao trong {grace_period}s: {resource_msg}')
                                    logger.error('   Force canceling PhoWhisper process...')
                                    monitoring_active.clear()
                                    cpu_monitor_queue.put(('cancel', {'cpu_percent': cpu_percent, 'memory_percent': memory_percent, 'reason': f'Resource quá cao trong {grace_period}s: {resource_msg}'}))
                                    return
                                else:
                                    remaining_time = grace_period - (time.time() - grace_start)
                                    resource_type = []
                                    if cpu_high:
                                        resource_type.append(f'CPU: {cpu_percent:.1f}%')
                                    if ram_high:
                                        resource_type.append(f'RAM: {memory_percent:.1f}%')
                                    resource_msg = ' + '.join(resource_type)
                                    logger.warning(f'⚠️ Resource vẫn cao: {resource_msg} (còn {remaining_time:.1f}s)')
                        elif consecutive_high_cpu > 0:
                            logger.info(f'✅ Resource đã trở lại bình thường: CPU {cpu_percent:.1f}%, RAM {memory_percent:.1f}%')
                            consecutive_high_cpu = 0
                            grace_start = None
                        time.sleep(1.0)
                    except Exception as e:
                        logger.error(f'❌ Lỗi trong CPU monitoring: {e}')
                        time.sleep(1.0)
            phowhisper_thread = threading.Thread(target=run_phowhisper, daemon=True)
            monitor_thread = threading.Thread(target=monitor_cpu, daemon=True)
            phowhisper_thread.start()
            monitor_thread.start()
            while True:
                try:
                    if not result_queue.empty():
                        result_type, result_data = result_queue.get_nowait()
                        if result_type == 'success':
                            monitoring_active.clear()
                            if not result_data.get('success'):
                                return {'success': False, 'message': result_data.get('message', 'PhoWhisper error')}
                            return {'success': True, 'transcript': result_data.get('transcript', ''), 'response': result_data, 'engine_used': 'phowhisper'}
                        else:
                            monitoring_active.clear()
                            return {'success': False, 'message': f'PhoWhisper error: {result_data}'}
                    if not cpu_monitor_queue.empty():
                        signal_type, signal_data = cpu_monitor_queue.get_nowait()
                        if signal_type == 'cancel':
                            monitoring_active.clear()
                            logger.error('🚨 Canceling PhoWhisper due to high CPU...')
                            phowhisper_thread.join(timeout=2.0)
                            return await self._fallback_to_deepgram(audio_path, audio_url, signal_data)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f'❌ Lỗi trong monitoring loop: {e}')
                    break
            monitoring_active.clear()
            return {'success': False, 'message': '❌ Monitoring loop error'}
        except Exception as e:
            logger.error(f'❌ Lỗi trong _run_phowhisper_with_monitoring: {e}')
            return {'success': False, 'message': f'❌ Monitoring error: {str(e)}'}

    async def _fallback_to_deepgram(self, audio_path: str, audio_url: str, cancel_data: dict):
        try:
            logger.info('🔄 Fallback sang Deepgram...')
            if self.telegram_bot:
                try:
                    fallback_message = f"\n✅ **FALLBACK SANG DEEPGRAM**\n\n🎵 **Audio:**\n`{audio_url}`\n\n📊 **Lý do:** {cancel_data.get('reason', 'Resource quá cao')}\n• CPU: {cancel_data.get('cpu_percent', 0):.1f}%\n• RAM: {cancel_data.get('memory_percent', 0):.1f}%\n\n🔄 **Đang chuyển sang Deepgram...**\n\n⏰ **Thời gian:** {time.strftime('%H:%M:%S %d/%m/%Y')}\n"
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(self.telegram_bot.send_message(chat_id=self.telegram_bot.admin_chat_id, text=fallback_message, parse_mode='Markdown'))
                        else:
                            asyncio.run(self.telegram_bot.send_message(chat_id=self.telegram_bot.admin_chat_id, text=fallback_message, parse_mode='Markdown'))
                    except RuntimeError:
                        import threading

                        def send_fallback_telegram():
                            try:
                                asyncio.run(self.telegram_bot.send_message(chat_id=self.telegram_bot.admin_chat_id, text=fallback_message, parse_mode='Markdown'))
                            except Exception as e:
                                logger.error(f'❌ Lỗi khi gửi fallback Telegram trong thread: {e}')
                        thread = threading.Thread(target=send_fallback_telegram, daemon=True)
                        thread.start()
                except Exception as e:
                    logger.error(f'❌ Lỗi khi gửi fallback notification: {e}')
            from stt_service import transcribe_prerecorded
            response = transcribe_prerecorded(self.deepgram_api_key, audio_path, {}, key_manager=self.deepgram_key_manager)
            if not response or 'results' not in response:
                return {'success': False, 'message': '❌ Response không hợp lệ từ Deepgram API (fallback)'}
            results = response.get('results', {})
            if 'channels' in results and len(results['channels']) > 0:
                channel = results['channels'][0]
                if 'alternatives' in channel and len(channel['alternatives']) > 0:
                    transcript = channel['alternatives'][0].get('transcript', '')
                else:
                    transcript = ''
            else:
                transcript = ''
            return {'success': True, 'transcript': transcript, 'response': response, 'engine_used': 'deepgram_fallback', 'fallback_reason': cancel_data.get('reason', 'CPU quá cao')}
        except Exception as e:
            logger.error(f'❌ Lỗi trong fallback: {e}')
            return {'success': False, 'message': f'❌ Fallback error: {str(e)}'}

    async def process_audio(self, audio_source, output_file='transcript_result.txt', trim_info=None):
        if DEBUG_MODE:
            logger.info(f'🚀 Bắt đầu xử lý audio từ: {audio_source}')
        try:
            duration_val = (trim_info or {}).get('duration', 0)
            billsec_val = (trim_info or {}).get('billsec', 0)
            if billsec_val < MIN_DURATION_THRESHOLD:
                if DEBUG_MODE:
                    logger.info(f'⛔ Bỏ qua xử lý: billsec={billsec_val}s < MIN_DURATION_THRESHOLD={MIN_DURATION_THRESHOLD}s')
                return {'success': False, 'message': f'Cuộc gọi quá ngắn (< {MIN_DURATION_THRESHOLD}s), bỏ qua xử lý', 'transcript': '', 'summary': '', 'call_topic': 'N/A'}
            if self.audio_processing_mode == 'off':
                resolved_path = audio_source
                if DEBUG_MODE:
                    logger.info(f'🔗 Chế độ OFF: Sử dụng URL trực tiếp: {resolved_path}')
            else:
                resolved_path = self._download_to_local(audio_source)
                if not resolved_path:
                    return {'success': False, 'message': '❌ Không thể tải file audio từ URL'}
                if DEBUG_MODE:
                    logger.info(f'✅ Đã tải file về: {resolved_path}')
            if not DISABLE_TRIM and duration_val and billsec_val and (not resolved_path.startswith(('http://', 'https://'))):
                if DEBUG_MODE:
                    logger.info(f'🔧 Bước 1.5: Trim audio - duration={duration_val}s, billsec={billsec_val}s (>= {MIN_DURATION_THRESHOLD}s)')
                resolved_path = await self._trim_audio(resolved_path, {'duration': duration_val, 'billsec': billsec_val})
                if not resolved_path:
                    return {'success': False, 'message': '❌ Không thể trim audio'}
            elif DEBUG_MODE:
                if DISABLE_TRIM:
                    logger.info('⚠️ Trim audio bị tắt (DISABLE_TRIM=True)')
                elif resolved_path.startswith(('http://', 'https://')):
                    logger.info('⚠️ Không thể trim URL trực tiếp (chế độ OFF)')
                else:
                    logger.info(f'⚠️ Không có thông tin trim hợp lệ: {trim_info}')
            if self.audio_processing_mode == 'off':
                if DEBUG_MODE:
                    logger.info('\n🔧 Chế độ OFF - bỏ qua phân tích và xử lý audio...')
                audio_meta = {'ok': True, 'warnings': [], 'suggested_options': {}}
            elif self.audio_processing_mode == 'auto':
                if DEBUG_MODE:
                    logger.info('\n🔍 Bước 1: Phân tích chất lượng audio (chế độ AUTO)...')
                audio_meta = analyze_audio_file(resolved_path)
                if audio_meta['ok']:
                    if DEBUG_MODE:
                        logger.info('✅ Chất lượng audio đạt yêu cầu - bỏ qua xử lý')
                    self.audio_processing_info.update({'normalization': False, 'noise_reduction': False, 'enhance_quality': False, 'silence_removal': False, 'compression': False, 'de_essing': False, 'de_reverb': False, 'processing_applied': False, 'skip_reason': 'Audio chất lượng tốt, không cần xử lý (AUTO mode)'})
                else:
                    if DEBUG_MODE:
                        logger.info('⚠️ Chất lượng audio không đạt yêu cầu - tiến hành xử lý')
                        logger.info('📋 Các vấn đề phát hiện:')
                        for warning in audio_meta['warnings']:
                            logger.info(f'   - {warning}')
                    if DEBUG_MODE:
                        logger.info(f'\n🔧 Bước 2: Xử lý audio với enhance_all (chế độ AUTO)...')
                    processed_path = await self._process_audio_quality(resolved_path)
                    if processed_path:
                        if DEBUG_MODE:
                            logger.info('✅ Đã xử lý audio, thử phân tích lại...')
                        new_audio_meta = analyze_audio_file(processed_path)
                        if new_audio_meta['ok']:
                            if DEBUG_MODE:
                                logger.info('✅ Chất lượng audio đã được cải thiện!')
                            resolved_path = processed_path
                            audio_meta = new_audio_meta
                        else:
                            if DEBUG_MODE:
                                logger.info('⚠️ Chất lượng vẫn chưa đạt sau khi xử lý')
                                logger.info('📋 Các vấn đề còn lại:')
                                for warning in new_audio_meta['warnings']:
                                    logger.info(f'   - {warning}')
                            if DEBUG_MODE:
                                logger.info('🤔 Chế độ AUTO: Quyết định chiến lược xử lý...')
                            original_issues = len(audio_meta.get('warnings', []))
                            processed_issues = len(new_audio_meta.get('warnings', []))
                            if processed_issues < original_issues:
                                if DEBUG_MODE:
                                    logger.info(f'📈 Chất lượng đã cải thiện: {original_issues} → {processed_issues} vấn đề')
                                    logger.info('✅ Sử dụng file đã xử lý (dù chưa hoàn hảo)')
                                resolved_path = processed_path
                                audio_meta = new_audio_meta
                                self.audio_processing_info.update({'processing_applied': True, 'quality_improved': True, 'remaining_issues': processed_issues, 'improvement_note': f'Giảm từ {original_issues} xuống {processed_issues} vấn đề'})
                            else:
                                if DEBUG_MODE:
                                    logger.info(f'📉 Chất lượng không cải thiện: {original_issues} → {processed_issues} vấn đề')
                                    logger.info('⚠️ Quay lại file gốc - gửi trực tiếp cho Deepgram (không xử lý nữa)')
                                    logger.info('📢 THÔNG BÁO: Audio sẽ được gửi trực tiếp cho Deepgram vì xử lý không hiệu quả')
                                try:
                                    from telegram_bot import telegram_bot
                                    if telegram_bot:
                                        notification_msg = f'⚠️ **Audio Processing Fallback**\n\n🔗 **URL**: {audio_source}\n📊 **Vấn đề**: {original_issues} → {processed_issues} vấn đề\n🔄 **Hành động**: Quay lại file gốc - gửi trực tiếp cho Deepgram\n📝 **Lý do**: Xử lý không cải thiện chất lượng'
                                        await telegram_bot.send_message(notification_msg)
                                except Exception as e:
                                    if DEBUG_MODE:
                                        logger.info(f'⚠️ Không thể gửi thông báo Telegram: {e}')
                                resolved_path = resolved_path
                                self.audio_processing_info.update({'processing_applied': False, 'quality_improved': False, 'processing_failed': True, 'fallback_to_original': True, 'failure_reason': f'Xử lý không hiệu quả: {original_issues} → {processed_issues} vấn đề'})
                    else:
                        if DEBUG_MODE:
                            logger.info('❌ Không thể xử lý audio, tiếp tục với file gốc...')
                        self.audio_processing_info.update({'processing_applied': False, 'processing_failed': True, 'failure_reason': 'Không thể tạo file đã xử lý'})
            else:
                if DEBUG_MODE:
                    logger.info('\n🔍 Bước 1: Phân tích chất lượng audio...')
                audio_meta = analyze_audio_file(resolved_path)
                if not audio_meta['ok']:
                    if DEBUG_MODE:
                        logger.info('⚠️ Chất lượng audio không đạt yêu cầu!')
                        for warning in audio_meta['warnings']:
                            logger.info(f'   - {warning}')
                    if DEBUG_MODE:
                        logger.info(f'\n🔧 Bước 2: Thử xử lý audio (chế độ: {self.audio_processing_mode})...')
                    processed_path = await self._process_audio_quality(resolved_path)
                    if processed_path:
                        if DEBUG_MODE:
                            logger.info('✅ Đã xử lý audio, thử phân tích lại...')
                        new_audio_meta = analyze_audio_file(processed_path)
                        if new_audio_meta['ok']:
                            if DEBUG_MODE:
                                logger.info('✅ Chất lượng audio đã được cải thiện!')
                            resolved_path = processed_path
                            audio_meta = new_audio_meta
                        elif DEBUG_MODE:
                            logger.info('⚠️ Chất lượng vẫn chưa đạt sau khi xử lý')
                            for warning in new_audio_meta['warnings']:
                                logger.info(f'   - {warning}')
                    elif DEBUG_MODE:
                        logger.info('❌ Không thể xử lý audio, tiếp tục với file gốc...')
                else:
                    if DEBUG_MODE:
                        logger.info('✅ Chất lượng audio đạt yêu cầu!')
                    if self.audio_processing_mode == 'enhance_all':
                        if DEBUG_MODE:
                            logger.info('🚀 Chế độ enhance_all: Audio chất lượng tốt → Bỏ qua xử lý, gửi trực tiếp lên Deepgram')
                        self.audio_processing_info.update({'normalization': False, 'noise_reduction': False, 'enhance_quality': False, 'silence_removal': False, 'compression': False, 'de_essing': False, 'de_reverb': False, 'processing_applied': False, 'skip_reason': 'Audio chất lượng tốt, không cần xử lý'})
            if DEBUG_MODE:
                logger.info('\n🎤 Bước 3: Chuyển đổi Speech-to-Text...')
            stt_result = await self._perform_stt(resolved_path, audio_meta, audio_url=audio_source)
            if not stt_result['success']:
                return stt_result
            if DEBUG_MODE:
                logger.info('\n📝 Bước 4: Tạo tóm tắt và phân loại nội dung...')
            summary_task = asyncio.create_task(self._create_summary(stt_result['transcript'], self.max_words))
            classification_task = asyncio.create_task(self._classify_content(stt_result['transcript']))
            summary_result, classification_result = await asyncio.gather(summary_task, classification_task)
            if DEBUG_MODE:
                logger.info('\n💾 Bước 5: Lưu kết quả...')
                self._save_results(output_file, audio_meta, stt_result, summary_result, classification_result)
                message = f'✅ Hoàn thành! Kết quả đã lưu vào {output_file}'
            else:
                if DEBUG_MODE:
                    logger.info('\n💾 Bước 5: Bỏ qua lưu file (debug_mode=false)...')
                message = '✅ Hoàn thành! Kết quả đã được xử lý'
            self._cleanup_processed_files()
            return {'success': True, 'message': message, 'transcript': stt_result['transcript'], 'summary': summary_result['summary'], 'call_topic': classification_result['call_topic']}
        except Exception as e:
            if DEBUG_MODE:
                logger.info(f'❌ Lỗi trong quá trình xử lý: {e}')
            self._cleanup_processed_files()
            return {'success': False, 'message': f'❌ Lỗi: {str(e)}'}

    async def _trim_audio(self, audio_path, trim_info):
        try:
            if DISABLE_TRIM:
                if DEBUG_MODE:
                    logger.info('⚠️ Trim audio bị tắt (DISABLE_TRIM=True)')
                return audio_path
            duration = trim_info.get('duration', 0)
            billsec = trim_info.get('billsec', 0)
            if duration <= MIN_DURATION_THRESHOLD or billsec <= MIN_DURATION_THRESHOLD or billsec >= duration:
                if DEBUG_MODE:
                    logger.info(f'⚠️ Thông tin trim không hợp lệ: duration={duration}s, billsec={billsec}s (MIN_DURATION_THRESHOLD={MIN_DURATION_THRESHOLD}s)')
                return audio_path
            trim_start = duration - billsec
            if trim_start <= 0:
                if DEBUG_MODE:
                    logger.info(f'ℹ️ Không cần trim: trim_start ({trim_start}s) <= 0s (không có thời gian đổ chuông)')
                return audio_path
            if DEBUG_MODE:
                logger.info(f'✂️ Trim audio: Cắt {trim_start}s đầu (đổ chuông), giữ lại {billsec}s cuộc hội thoại')
            from pathlib import Path
            input_path = Path(audio_path)
            output_path = str(input_path.parent / f'{input_path.stem}_trimmed{input_path.suffix}')
            import subprocess
            cmd = ['ffmpeg', '-y', '-i', audio_path, '-ss', str(trim_start), '-c', 'copy', output_path]
            if DEBUG_MODE:
                logger.info(f"🔧 Chạy lệnh: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and os.path.exists(output_path) and (os.path.getsize(output_path) > 0):
                if DEBUG_MODE:
                    logger.info(f'✅ Trim audio thành công: {output_path}')
                self.processed_files.append(output_path)
                self.audio_processing_info.update({'trim_applied': True, 'trim_start_seconds': trim_start, 'trim_duration_seconds': billsec, 'trim_reason': f'Loại bỏ {trim_start}s đổ chuông, giữ lại {billsec}s cuộc hội thoại'})
                return output_path
            else:
                if DEBUG_MODE:
                    logger.info(f'❌ Trim audio thất bại: {result.stderr}')
                return None
        except FileNotFoundError:
            if DEBUG_MODE:
                logger.info('❌ sox không được cài đặt - không thể trim audio')
            return audio_path
        except Exception as e:
            if DEBUG_MODE:
                logger.info(f'❌ Lỗi khi trim audio: {e}')
            return None

    def _resolve_input_source(self, audio_source):
        return self._download_to_local(audio_source)

    def _download_to_local(self, audio_source: str) -> str:
        try:
            if not audio_source.startswith(('http://', 'https://')):
                logger.warning(f'❌ Chỉ hỗ trợ URL, không hỗ trợ file local: {audio_source}')
                return None
            os.makedirs('resource', exist_ok=True)
            output_path = 'resource/downloaded_audio.wav'
            if self._download_with_ffmpeg(audio_source, output_path):
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f'✅ Đã tải file thành công bằng ffmpeg: {output_path}')
                    self.processed_files.append(output_path)
                    return output_path
            logger.info('🔄 FFmpeg thất bại, thử curl...')
            if self._download_with_curl(audio_source, output_path):
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    logger.info(f'✅ Đã tải file thành công bằng curl: {output_path}')
                    self.processed_files.append(output_path)
                    return output_path
            logger.error(f'❌ Không thể tải file từ URL: {audio_source}')
            return None
        except Exception as e:
            logger.error(f'❌ Lỗi khi tải file từ URL: {e}')
            return None

    def _download_with_ffmpeg(self, audio_source: str, output_path: str) -> bool:
        try:
            import subprocess
            cmd = ['ffmpeg', '-y', '-i', audio_source, '-ac', '1', '-ar', '16000', output_path]
            if DEBUG_MODE:
                logger.info(f"📥 Tải bằng ffmpeg: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                if DEBUG_MODE:
                    logger.error(f'❌ Lỗi ffmpeg khi tải: {result.stderr}')
                return False
            return True
        except FileNotFoundError:
            logger.warning('⚠️ FFmpeg không được cài đặt, sẽ thử curl')
            return False
        except Exception as e:
            logger.error(f'❌ Lỗi ffmpeg: {e}')
            return False

    def _download_with_curl(self, audio_source: str, output_path: str) -> bool:
        try:
            import subprocess
            cmd = ['curl', '-L', '-o', output_path, '--connect-timeout', '30', '--max-time', '120', '--fail', audio_source]
            if DEBUG_MODE:
                logger.info(f"📥 Tải bằng curl: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                if DEBUG_MODE:
                    logger.error(f'❌ Lỗi curl khi tải: {result.stderr}')
                return False
            return True
        except FileNotFoundError:
            logger.error('❌ Cả ffmpeg và curl đều không được cài đặt')
            return False
        except Exception as e:
            logger.error(f'❌ Lỗi curl: {e}')
            return False

    async def _process_audio_quality(self, audio_path):
        try:
            actual_processing_mode = self.audio_processing_mode
            if self.audio_processing_mode == 'auto':
                actual_processing_mode = 'enhance_all'
                if DEBUG_MODE:
                    logger.info(f'   🔄 Chế độ AUTO: Sử dụng enhance_all để cải thiện chất lượng')
            result = process_audio_comprehensive(audio_path, processing_mode=actual_processing_mode)
            if result['success']:
                if 'temp_files' in result:
                    self.processed_files.extend(result['temp_files'])
                self.audio_processing_info.update(result['processing_info'])
                if DEBUG_MODE:
                    logger.info(f"   ✅ {result['message']}")
                return result['output_file']
            else:
                if DEBUG_MODE:
                    logger.info(f"   ❌ {result['message']}")
                return None
        except Exception as e:
            if DEBUG_MODE:
                logger.info(f'   ❌ Lỗi khi xử lý audio: {e}')
            return None

    async def _perform_stt(self, audio_path, audio_meta, audio_url=None):
        try:
            if getattr(self, 'engine', 'deepgram') == 'phowhisper':
                logger.info('🎯 Chạy PhoWhisper transcription với CPU monitoring...')
                if audio_url:
                    return await self._run_phowhisper_with_monitoring(audio_path, audio_url)
                else:
                    from phowhisper_engine import transcribe as pw_transcribe
                    pw_result = pw_transcribe(audio_path)
                    if not pw_result.get('success'):
                        return {'success': False, 'message': pw_result.get('message', 'PhoWhisper error')}
                    return {'success': True, 'transcript': pw_result.get('transcript', ''), 'response': pw_result, 'engine_used': 'phowhisper'}
            else:
                suggested_options = audio_meta.get('suggested_options', {})
                response = transcribe_prerecorded(self.deepgram_api_key, audio_path, suggested_options, key_manager=self.deepgram_key_manager)
                if not response or 'results' not in response:
                    return {'success': False, 'message': '❌ Response không hợp lệ từ Deepgram API'}
                results = response.get('results', {})
                if 'channels' in results and len(results['channels']) > 0:
                    channel = results['channels'][0]
                    if 'alternatives' in channel and len(channel['alternatives']) > 0:
                        transcript = channel['alternatives'][0].get('transcript', '')
                    else:
                        transcript = ''
                else:
                    transcript = ''
                return {'success': True, 'transcript': transcript, 'response': response, 'engine_used': 'deepgram'}
        except Exception as e:
            return {'success': False, 'message': f'❌ Lỗi STT: {str(e)}'}

    async def _create_summary(self, transcript, max_words=None):
        try:
            current_max_words = max_words or self.max_words
            summary_method = get_summary_method('', self.google_api_key)
            if summary_method == 'google_ai' and self.google_api_key:
                if DEBUG_MODE:
                    logger.info('🤖 Sử dụng Google AI (Gemini) Summarization...')
                summary = await summarize_with_google_ai(self.google_api_key, transcript.strip(), max_words=current_max_words, key_manager=self.google_key_manager)
                if not summary:
                    if DEBUG_MODE:
                        logger.info('⚠️ Google AI summarization thất bại, chuyển sang thuật toán...')
                    summary = summarize_transcript(transcript.strip(), max_words=current_max_words)
                    summary_method = 'algorithm'
                else:
                    summary_method = 'google_ai'
            else:
                if DEBUG_MODE:
                    logger.info('📝 Sử dụng thuật toán tóm tắt...')
                summary = summarize_transcript(transcript.strip(), max_words=current_max_words)
                summary_method = 'algorithm'
            return {'success': True, 'summary': summary, 'method': summary_method}
        except Exception as e:
            return {'success': False, 'summary': f'❌ Lỗi tạo tóm tắt: {str(e)}', 'method': 'error'}

    async def _classify_content(self, transcript):
        try:
            if DEBUG_MODE:
                logger.info('🔍 Bắt đầu phân loại nội dung...')
            call_topic = await classify_conversation_content(text=transcript.strip(), api_key=self.google_api_key, use_few_shot=False, key_manager=self.classifier_key_manager)
            if DEBUG_MODE:
                logger.info(f'📊 Kết quả phân loại: {call_topic}')
            return {'success': True, 'call_topic': call_topic}
        except Exception as e:
            if DEBUG_MODE:
                logger.info(f'❌ Lỗi phân loại nội dung: {str(e)}')
            return {'success': False, 'call_topic': 'N/A'}

    def _save_results(self, output_file, audio_meta, stt_result, summary_result, classification_result=None):
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write('=' * 50 + '\n')
                f.write('AUDIO METADATA\n')
                f.write('=' * 50 + '\n')
                for key, value in audio_meta.items():
                    if key not in ['warnings', 'suggested_options', 'ok']:
                        f.write(f'{key}: {value}\n')
                if not audio_meta.get('ok', True):
                    f.write('Chất lượng audio: Không đạt yêu cầu')
                    if audio_meta.get('warnings'):
                        for warning in audio_meta['warnings']:
                            f.write(f' (do {warning})')
                    f.write('\n')
                else:
                    f.write('Chất lượng audio: Đạt yêu cầu\n')
                applied_techniques = []
                if self.audio_processing_info['enhance_quality'] and self.audio_processing_info['normalization'] and self.audio_processing_info['noise_reduction'] and self.audio_processing_info['silence_removal'] and self.audio_processing_info['compression'] and self.audio_processing_info['de_reverb'] and self.audio_processing_info['de_essing']:
                    applied_techniques = ['Chuẩn hóa định dạng (Format Standardization)', 'Loại bỏ tạp âm (Noise Reduction)', 'Ngắt quãng và chồng chéo (Silence Removal)', 'Compression âm lượng (Dynamic Range Compression)', 'De-reverb (giảm tiếng vang)', 'De-essing (loại bỏ tiếng s, sh)']
                else:
                    if self.audio_processing_info['normalization']:
                        applied_techniques.append('Chuẩn hóa định dạng (Format Standardization)')
                    if self.audio_processing_info['enhance_quality']:
                        applied_techniques.append('Cải thiện chất lượng audio tổng thể')
                    if self.audio_processing_info['noise_reduction']:
                        applied_techniques.append('Loại bỏ tạp âm (Noise Reduction)')
                    if self.audio_processing_info['silence_removal']:
                        applied_techniques.append('Ngắt quãng và chồng chéo (Silence Removal)')
                    if self.audio_processing_info['compression']:
                        applied_techniques.append('Compression âm lượng (Dynamic Range Compression)')
                    if self.audio_processing_info['de_reverb']:
                        applied_techniques.append('De-reverb (giảm tiếng vang)')
                    if self.audio_processing_info['de_essing']:
                        applied_techniques.append('De-essing (loại bỏ tiếng s, sh)')
                if self.audio_processing_info.get('trim_applied'):
                    f.write('Đã áp dụng trim audio: Có\n')
                    f.write(f"Lý do trim: {self.audio_processing_info.get('trim_reason', 'N/A')}\n")
                    f.write(f"Thời gian cắt đầu: {self.audio_processing_info.get('trim_start_seconds', 0)}s\n")
                    f.write(f"Thời gian cuộc hội thoại: {self.audio_processing_info.get('trim_duration_seconds', 0)}s\n")
                else:
                    f.write('Đã áp dụng trim audio: Không\n')
                if applied_techniques:
                    f.write('Đã áp dụng xử lý audio: Có\n')
                    f.write('Các kỹ thuật đã áp dụng:\n')
                    for i, technique in enumerate(applied_techniques, 1):
                        f.write(f'{i}. {technique}\n')
                    if self.audio_processing_info.get('quality_improved'):
                        f.write(f"Kết quả cải thiện: {self.audio_processing_info.get('improvement_note', 'N/A')}\n")
                        f.write(f"Vấn đề còn lại: {self.audio_processing_info.get('remaining_issues', 0)}\n")
                else:
                    f.write('Đã áp dụng xử lý audio: Không\n')
                    if self.audio_processing_info.get('skip_reason'):
                        f.write(f"Lý do bỏ qua: {self.audio_processing_info['skip_reason']}\n")
                    if self.audio_processing_info.get('processing_failed'):
                        f.write(f"Lý do xử lý thất bại: {self.audio_processing_info.get('failure_reason', 'N/A')}\n")
                        if self.audio_processing_info.get('fallback_to_original'):
                            f.write('🔄 Hành động: Quay lại file gốc - gửi trực tiếp cho Deepgram\n')
                if audio_meta.get('warnings'):
                    f.write('\nWarnings:\n')
                    for warning in audio_meta['warnings']:
                        f.write(f'- {warning}\n')
                f.write('\n' + '=' * 50 + '\n')
                f.write('TRANSCRIPTION METADATA\n')
                f.write('=' * 50 + '\n')
                if 'response' in stt_result:
                    response = stt_result['response']
                    f.write(f"Model: {response.get('metadata', {}).get('model_info', 'N/A')}\n")
                    f.write(f"Language: {response.get('metadata', {}).get('language_info', 'N/A')}\n")
                    f.write(f"Duration: {response.get('metadata', {}).get('duration', 'N/A')}s\n")
                    f.write(f"Channels: {response.get('metadata', {}).get('channels', 'N/A')}\n")
                f.write('\n' + '=' * 50 + '\n')
                f.write(f"TRANSCRIPT ({len(stt_result['transcript'])} ký tự)\n")
                f.write('=' * 50 + '\n')
                f.write(stt_result['transcript'] + '\n')
                f.write('\n' + '=' * 50 + '\n')
                f.write('DIỄN BIẾN CHI TIẾT\n')
                f.write('=' * 50 + '\n')
                self._write_detailed_timeline(f, stt_result)
                f.write('\n' + '=' * 50 + '\n')
                f.write(f"Tổng hợp nội dung cuộc hội thoại ({len(summary_result['summary'])} ký tự):\n")
                f.write('=' * 50 + '\n')
                f.write(f"Phương pháp: {summary_result.get('method', 'UNKNOWN').upper()}\n")
                f.write('-' * 30 + '\n')
                f.write(summary_result['summary'] + '\n')
                if classification_result:
                    f.write('\n' + '=' * 50 + '\n')
                    f.write('PHÂN LOẠI NỘI DUNG\n')
                    f.write('=' * 50 + '\n')
                    f.write(f"Chủ đề cuộc gọi: {classification_result.get('call_topic', 'N/A')}\n")
                    f.write(f"Trạng thái: {('Thành công' if classification_result.get('success', False) else 'Thất bại')}\n")
            if DEBUG_MODE:
                logger.info(f'✅ Đã lưu kết quả vào: {output_file}')
        except Exception as e:
            if DEBUG_MODE:
                logger.info(f'❌ Lỗi khi lưu file: {e}')

    def _write_detailed_timeline(self, f, stt_result):
        try:
            if 'response' not in stt_result:
                return
            response = stt_result['response']
            utterances = response.get('results', {}).get('utterances', [])
            if not utterances:
                words = response.get('results', {}).get('channels', [{}])[0].get('alternatives', [{}])[0].get('words', [])
                if words:
                    self._write_words_timeline(f, words)
                return
            for i, utterance in enumerate(utterances, 1):
                speaker = utterance.get('speaker', 0)
                speaker_name = 'NVTĐ' if speaker == 0 else f'KH {speaker}'
                start_time = utterance.get('start', 0)
                end_time = utterance.get('end', 0)
                confidence = utterance.get('confidence', 0)
                text = utterance.get('transcript', '')
                start_min = int(start_time // 60)
                start_sec = int(start_time % 60)
                end_min = int(end_time // 60)
                end_sec = int(end_time % 60)
                display_text = text
                if len(display_text) > 80:
                    display_text = display_text[:80] + '...'
                f.write(f' {i:2d}. [{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}] {speaker_name} ({confidence:.1%}): {display_text}\n')
        except Exception as e:
            f.write(f'❌ Lỗi khi tạo timeline: {str(e)}\n')

    def _write_words_timeline(self, f, words):
        try:
            current_speaker = 0
            current_text = ''
            current_start = 0
            current_end = 0
            utterance_count = 0
            for word in words:
                if hasattr(word, 'speaker'):
                    speaker = word.speaker
                    start_time = word.start
                    end_time = word.end
                    word_text = word.word
                else:
                    speaker = word.get('speaker', 0)
                    start_time = word.get('start', 0)
                    end_time = word.get('end', 0)
                    word_text = word.get('word', '')
                if speaker != current_speaker or (current_text and start_time - current_end > 2.0):
                    if current_text:
                        utterance_count += 1
                        speaker_name = 'NVTĐ' if current_speaker == 0 else f'KH {current_speaker}'
                        start_min = int(current_start // 60)
                        start_sec = int(current_start % 60)
                        end_min = int(current_end // 60)
                        end_sec = int(current_end % 60)
                        display_text = current_text
                        if len(display_text) > 80:
                            display_text = display_text[:80] + '...'
                        f.write(f' {utterance_count:2d}. [{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}] {speaker_name}: {display_text}\n')
                    current_speaker = speaker
                    current_text = word_text
                    current_start = start_time
                    current_end = end_time
                else:
                    current_text += ' ' + word_text
                    current_end = end_time
            if current_text:
                utterance_count += 1
                speaker_name = 'NVTĐ' if current_speaker == 0 else f'KH {current_speaker}'
                start_min = int(current_start // 60)
                start_sec = int(current_start % 60)
                end_min = int(current_end // 60)
                end_sec = int(current_end % 60)
                display_text = current_text
                if len(display_text) > 80:
                    display_text = display_text[:80] + '...'
                f.write(f' {utterance_count:2d}. [{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}] {speaker_name}: {display_text}\n')
        except Exception as e:
            f.write(f'❌ Lỗi khi tạo words timeline: {str(e)}\n')

    def _cleanup_processed_files(self):
        for file_path in self.processed_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    if DEBUG_MODE:
                        logger.info(f'🗑️ Đã xóa file tạm: {file_path}')
            except Exception as e:
                if DEBUG_MODE:
                    logger.info(f'⚠️ Không thể xóa file {file_path}: {e}')
        self.processed_files.clear()