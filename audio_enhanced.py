import os
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from config import AUDIO_PROCESSING_MODE
logger = logging.getLogger(__name__)

def _validate_file_and_get_output(input_file, output_file=None, suffix='_processed'):
    if output_file is None:
        input_path = Path(input_file)
        output_file = str(input_path.parent / f'{input_path.stem}{suffix}{input_path.suffix}')
    return {'success': True, 'output_file': output_file, 'message': None}

def _normalize_audio_format(input_file, output_file=None):
    validation = _validate_file_and_get_output(input_file, output_file, '_normalized')
    output_file = validation['output_file']
    try:
        cmd = ['sox', input_file, output_file, 'rate', '16000', 'channels', '1', 'norm']
        logger.info(f'🔧 Đang chuẩn hóa định dạng audio...')
        logger.info(f'   Input: {input_file}')
        logger.info(f'   Output: {output_file}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return {'success': True, 'output_file': output_file, 'message': f'✅ Chuẩn hóa định dạng thành công: {output_file}'}
            else:
                return {'success': False, 'output_file': None, 'message': '❌ File output không được tạo hoặc rỗng'}
        else:
            return {'success': False, 'output_file': None, 'message': f'❌ Lỗi khi chuẩn hóa định dạng: {result.stderr}'}
    except FileNotFoundError:
        return {'success': False, 'output_file': None, 'message': '❌ sox không được cài đặt'}
    except Exception as e:
        return {'success': False, 'output_file': None, 'message': f'❌ Lỗi không xác định: {str(e)}'}

def reduce_noise(input_file, output_file=None):
    validation = _validate_file_and_get_output(input_file, output_file, '_noise_reduced')
    output_file = validation['output_file']
    try:
        cmd = ['sox', input_file, output_file, 'highpass', '80', 'lowpass', '8000']
        logger.info(f'🔧 Đang xử lý noise reduction...')
        logger.info(f'   Input: {input_file}')
        logger.info(f'   Output: {output_file}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return {'success': True, 'output_file': output_file, 'message': f'✅ Xử lý noise reduction thành công: {output_file}'}
            else:
                return {'success': False, 'output_file': None, 'message': '❌ File output không được tạo hoặc rỗng'}
        else:
            return {'success': False, 'output_file': None, 'message': f'❌ Lỗi khi xử lý noise reduction: {result.stderr}'}
    except FileNotFoundError:
        return {'success': False, 'output_file': None, 'message': '❌ sox không được cài đặt'}
    except Exception as e:
        return {'success': False, 'output_file': None, 'message': f'❌ Lỗi không xác định: {str(e)}'}

def remove_silence_and_gaps(input_file, output_file=None):
    validation = _validate_file_and_get_output(input_file, output_file, '_silence_removed')
    output_file = validation['output_file']
    try:
        cmd = ['sox', input_file, output_file, 'silence', '1', '0.1', '1%', 'reverse', 'silence', '1', '0.1', '1%', 'reverse']
        logger.info(f'🔧 Đang xử lý ngắt quãng và chồng chéo...')
        logger.info(f'   Input: {input_file}')
        logger.info(f'   Output: {output_file}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return {'success': True, 'output_file': output_file, 'message': f'✅ Xử lý ngắt quãng thành công: {output_file}'}
            else:
                return {'success': False, 'output_file': None, 'message': '❌ File output không được tạo hoặc rỗng'}
        else:
            return {'success': False, 'output_file': None, 'message': f'❌ Lỗi khi xử lý ngắt quãng: {result.stderr}'}
    except FileNotFoundError:
        return {'success': False, 'output_file': None, 'message': '❌ sox không được cài đặt'}
    except Exception as e:
        return {'success': False, 'output_file': None, 'message': f'❌ Lỗi không xác định: {str(e)}'}

def apply_compression(input_file, output_file=None):
    validation = _validate_file_and_get_output(input_file, output_file, '_compressed')
    output_file = validation['output_file']
    try:
        cmd = ['sox', input_file, output_file, 'compand', '0.3,1', '6:-70,-60,-20', '-5', '-90', '0.2']
        logger.info(f'🔧 Đang áp dụng compression...')
        logger.info(f'   Input: {input_file}')
        logger.info(f'   Output: {output_file}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return {'success': True, 'output_file': output_file, 'message': f'✅ Áp dụng compression thành công: {output_file}'}
            else:
                return {'success': False, 'output_file': None, 'message': '❌ File output không được tạo hoặc rỗng'}
        else:
            return {'success': False, 'output_file': None, 'message': f'❌ Lỗi khi áp dụng compression: {result.stderr}'}
    except FileNotFoundError:
        return {'success': False, 'output_file': None, 'message': '❌ sox không được cài đặt'}
    except Exception as e:
        return {'success': False, 'output_file': None, 'message': f'❌ Lỗi không xác định: {str(e)}'}

def apply_de_reverb(input_file, output_file=None):
    validation = _validate_file_and_get_output(input_file, output_file, '_dereverb')
    output_file = validation['output_file']
    try:
        cmd = ['sox', input_file, output_file, 'highpass', '150', 'lowpass', '8000', 'compand', '0.1,1', '6:-70,-60,-20', '-10', '-90', '0.1']
        logger.info(f'🔧 Đang áp dụng de-reverb...')
        logger.info(f'   Input: {input_file}')
        logger.info(f'   Output: {output_file}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return {'success': True, 'output_file': output_file, 'message': f'✅ Áp dụng de-reverb thành công: {output_file}'}
            else:
                return {'success': False, 'output_file': None, 'message': '❌ File output không được tạo hoặc rỗng'}
        else:
            return {'success': False, 'output_file': None, 'message': f'❌ Lỗi khi áp dụng de-reverb: {result.stderr}'}
    except FileNotFoundError:
        return {'success': False, 'output_file': None, 'message': '❌ sox không được cài đặt'}
    except Exception as e:
        return {'success': False, 'output_file': None, 'message': f'❌ Lỗi không xác định: {str(e)}'}

def apply_de_essing(input_file, output_file=None):
    validation = _validate_file_and_get_output(input_file, output_file, '_deessed')
    output_file = validation['output_file']
    try:
        cmd = ['sox', input_file, output_file, 'highpass', '80', 'lowpass', '7000', 'compand', '0.3,1', '6:-70,-60,-20', '-5', '-90', '0.2']
        logger.info(f'🔧 Đang áp dụng de-essing...')
        logger.info(f'   Input: {input_file}')
        logger.info(f'   Output: {output_file}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return {'success': True, 'output_file': output_file, 'message': f'✅ Áp dụng de-essing thành công: {output_file}'}
            else:
                return {'success': False, 'output_file': None, 'message': '❌ File output không được tạo hoặc rỗng'}
        else:
            return {'success': False, 'output_file': None, 'message': f'❌ Lỗi khi áp dụng de-essing: {result.stderr}'}
    except FileNotFoundError:
        return {'success': False, 'output_file': None, 'message': '❌ sox không được cài đặt'}
    except Exception as e:
        return {'success': False, 'output_file': None, 'message': f'❌ Lỗi không xác định: {str(e)}'}

def enhance_audio_quality(input_file, output_file=None):
    validation = _validate_file_and_get_output(input_file, output_file, '_enhanced')
    output_file = validation['output_file']
    try:
        cmd = ['sox', input_file, output_file, 'rate', '16000', 'channels', '1', 'norm', 'highpass', '80', 'lowpass', '8000', 'silence', '1', '0.1', '1%', 'reverse', 'silence', '1', '0.1', '1%', 'reverse', 'compand', '0.3,1', '6:-70,-60,-20', '-5', '-90', '0.2', 'highpass', '150', 'lowpass', '7000', 'compand', '0.1,1', '6:-70,-60,-20', '-10', '-90', '0.1']
        logger.info(f'🔧 Đang cải thiện chất lượng audio tổng thể...')
        logger.info(f'   Input: {input_file}')
        logger.info(f'   Output: {output_file}')
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                return {'success': True, 'output_file': output_file, 'message': f'✅ Cải thiện chất lượng tổng thể thành công: {output_file}'}
            else:
                return {'success': False, 'output_file': None, 'message': '❌ File output không được tạo hoặc rỗng'}
        else:
            return {'success': False, 'output_file': None, 'message': f'❌ Lỗi khi cải thiện chất lượng: {result.stderr}'}
    except FileNotFoundError:
        return {'success': False, 'output_file': None, 'message': '❌ sox không được cài đặt'}
    except Exception as e:
        return {'success': False, 'output_file': None, 'message': f'❌ Lỗi không xác định: {str(e)}'}

def process_audio_comprehensive(input_file, output_file=None, processing_mode=None):
    try:
        subprocess.run(['sox', '--version'], capture_output=True, check=True)
        sox_available = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        sox_available = False
        logger.info('   ⚠️ sox không được cài đặt, bỏ qua xử lý audio')
    if not sox_available:
        return {'success': False, 'output_file': None, 'message': '❌ sox không được cài đặt. Vui lòng cài đặt sox để sử dụng tính năng xử lý audio.', 'processing_info': {'noise_reduction': False, 'enhance_quality': False, 'silence_removal': False, 'compression': False, 'de_essing': False, 'de_reverb': False, 'processing_applied': False, 'processing_mode': processing_mode}}
    if processing_mode is None:
        processing_mode = AUDIO_PROCESSING_MODE
    processing_info = {'noise_reduction': False, 'enhance_quality': False, 'silence_removal': False, 'compression': False, 'de_essing': False, 'de_reverb': False, 'processing_applied': False, 'processing_mode': processing_mode}
    try:
        current_input = input_file
        temp_files = []
        if processing_mode == 'enhance_all':
            logger.info('🔧 Chế độ: Áp dụng tất cả các kỹ thuật xử lý audio...')
            logger.info('   🔧 Bước 1: Cải thiện chất lượng audio tổng thể (bao gồm tất cả kỹ thuật)...')
            enhance_result = enhance_audio_quality(current_input, output_file)
            if enhance_result['success']:
                processing_info['normalization'] = True
                processing_info['noise_reduction'] = True
                processing_info['silence_removal'] = True
                processing_info['compression'] = True
                processing_info['de_reverb'] = True
                processing_info['de_essing'] = True
                processing_info['enhance_quality'] = True
                processing_info['processing_applied'] = True
                current_input = enhance_result['output_file']
                temp_files.append(current_input)
                logger.info('   ✅ Cải thiện chất lượng tổng thể thành công')
                return {'success': True, 'output_file': current_input, 'message': f'✅ Xử lý audio hoàn thành với tất cả các kỹ thuật', 'processing_info': processing_info, 'temp_files': temp_files}
            else:
                logger.info(f"   ⚠️ Cải thiện chất lượng thất bại: {enhance_result['message']}")
                return {'success': False, 'output_file': None, 'message': '❌ Không thể cải thiện chất lượng audio', 'processing_info': processing_info, 'temp_files': temp_files}
        elif processing_mode == 'noise_only':
            logger.info('🔧 Chế độ: Chỉ xử lý noise reduction...')
            normalize_result = _normalize_audio_format(current_input)
            if normalize_result['success']:
                current_input = normalize_result['output_file']
                temp_files.append(current_input)
                processing_info['normalization'] = True
                logger.info('   ✅ Chuẩn hóa định dạng thành công')
            else:
                logger.info(f"   ⚠️ Chuẩn hóa định dạng thất bại: {normalize_result['message']}")
                return {'success': False, 'output_file': None, 'message': '❌ Không thể chuẩn hóa định dạng audio', 'processing_info': processing_info, 'temp_files': temp_files}
            result = reduce_noise(current_input, output_file)
            if result['success']:
                processing_info['noise_reduction'] = True
                processing_info['processing_applied'] = True
                if result['output_file'] and result['output_file'] != current_input:
                    temp_files.append(result['output_file'])
            return {'success': result['success'], 'output_file': result['output_file'], 'message': result['message'], 'processing_info': processing_info, 'temp_files': temp_files}
        elif processing_mode == 'silence_only':
            logger.info('🔧 Chế độ: Chỉ xử lý silence removal...')
            normalize_result = _normalize_audio_format(current_input)
            if normalize_result['success']:
                current_input = normalize_result['output_file']
                temp_files.append(current_input)
                processing_info['normalization'] = True
                logger.info('   ✅ Chuẩn hóa định dạng thành công')
            else:
                logger.info(f"   ⚠️ Chuẩn hóa định dạng thất bại: {normalize_result['message']}")
                return {'success': False, 'output_file': None, 'message': '❌ Không thể chuẩn hóa định dạng audio', 'processing_info': processing_info, 'temp_files': temp_files}
            result = remove_silence_and_gaps(current_input, output_file)
            if result['success']:
                processing_info['silence_removal'] = True
                processing_info['processing_applied'] = True
                if result['output_file'] and result['output_file'] != current_input:
                    temp_files.append(result['output_file'])
            return {'success': result['success'], 'output_file': result['output_file'], 'message': result['message'], 'processing_info': processing_info, 'temp_files': temp_files}
        elif processing_mode == 'compression_only':
            logger.info('🔧 Chế độ: Chỉ áp dụng compression...')
            normalize_result = _normalize_audio_format(current_input)
            if normalize_result['success']:
                current_input = normalize_result['output_file']
                temp_files.append(current_input)
                processing_info['normalization'] = True
                logger.info('   ✅ Chuẩn hóa định dạng thành công')
            else:
                logger.info(f"   ⚠️ Chuẩn hóa định dạng thất bại: {normalize_result['message']}")
                return {'success': False, 'output_file': None, 'message': '❌ Không thể chuẩn hóa định dạng audio', 'processing_info': processing_info, 'temp_files': temp_files}
            result = apply_compression(current_input, output_file)
            if result['success']:
                processing_info['compression'] = True
                processing_info['processing_applied'] = True
                if result['output_file'] and result['output_file'] != current_input:
                    temp_files.append(result['output_file'])
            return {'success': result['success'], 'output_file': result['output_file'], 'message': result['message'], 'processing_info': processing_info, 'temp_files': temp_files}
        elif processing_mode == 'de_reverb_only':
            logger.info('🔧 Chế độ: Chỉ áp dụng de-reverb...')
            normalize_result = _normalize_audio_format(current_input)
            if normalize_result['success']:
                current_input = normalize_result['output_file']
                temp_files.append(current_input)
                processing_info['normalization'] = True
                logger.info('   ✅ Chuẩn hóa định dạng thành công')
            else:
                logger.info(f"   ⚠️ Chuẩn hóa định dạng thất bại: {normalize_result['message']}")
                return {'success': False, 'output_file': None, 'message': '❌ Không thể chuẩn hóa định dạng audio', 'processing_info': processing_info, 'temp_files': temp_files}
            result = apply_de_reverb(current_input, output_file)
            if result['success']:
                processing_info['de_reverb'] = True
                processing_info['processing_applied'] = True
                if result['output_file'] and result['output_file'] != current_input:
                    temp_files.append(result['output_file'])
            return {'success': result['success'], 'output_file': result['output_file'], 'message': result['message'], 'processing_info': processing_info, 'temp_files': temp_files}
        elif processing_mode == 'de_essing_only':
            logger.info('🔧 Chế độ: Chỉ áp dụng de-essing...')
            normalize_result = _normalize_audio_format(current_input)
            if normalize_result['success']:
                current_input = normalize_result['output_file']
                temp_files.append(current_input)
                processing_info['normalization'] = True
                logger.info('   ✅ Chuẩn hóa định dạng thành công')
            else:
                logger.info(f"   ⚠️ Chuẩn hóa định dạng thất bại: {normalize_result['message']}")
                return {'success': False, 'output_file': None, 'message': '❌ Không thể chuẩn hóa định dạng audio', 'processing_info': processing_info, 'temp_files': temp_files}
            result = apply_de_essing(current_input, output_file)
            if result['success']:
                processing_info['de_essing'] = True
                processing_info['processing_applied'] = True
                if result['output_file'] and result['output_file'] != current_input:
                    temp_files.append(result['output_file'])
            return {'success': result['success'], 'output_file': result['output_file'], 'message': result['message'], 'processing_info': processing_info, 'temp_files': temp_files}
        elif isinstance(processing_mode, list):
            logger.info(f'🔧 Chế độ: Xử lý nhiều phương pháp: {processing_mode}')
            current_input = input_file
            temp_files = []
            applied_methods = []
            for method in processing_mode:
                if method == 'noise_only':
                    logger.info('   🔧 Xử lý noise reduction...')
                    result = reduce_noise(current_input)
                    if result['success']:
                        processing_info['noise_reduction'] = True
                        processing_info['processing_applied'] = True
                        current_input = result['output_file']
                        temp_files.append(current_input)
                        applied_methods.append('noise_reduction')
                        logger.info('   ✅ Noise reduction thành công')
                    else:
                        logger.info(f"   ⚠️ Noise reduction thất bại: {result['message']}")
                elif method == 'silence_only':
                    logger.info('   🔧 Xử lý silence removal...')
                    result = remove_silence_and_gaps(current_input)
                    if result['success']:
                        processing_info['silence_removal'] = True
                        processing_info['processing_applied'] = True
                        current_input = result['output_file']
                        temp_files.append(current_input)
                        applied_methods.append('silence_removal')
                        logger.info('   ✅ Silence removal thành công')
                    else:
                        logger.info(f"   ⚠️ Silence removal thất bại: {result['message']}")
                elif method == 'compression_only':
                    logger.info('   🔧 Xử lý compression...')
                    result = apply_compression(current_input)
                    if result['success']:
                        processing_info['compression'] = True
                        processing_info['processing_applied'] = True
                        current_input = result['output_file']
                        temp_files.append(current_input)
                        applied_methods.append('compression')
                        logger.info('   ✅ Compression thành công')
                    else:
                        logger.info(f"   ⚠️ Compression thất bại: {result['message']}")
                elif method == 'de_reverb_only':
                    logger.info('   🔧 Xử lý de-reverb...')
                    result = apply_de_reverb(current_input)
                    if result['success']:
                        processing_info['de_reverb'] = True
                        processing_info['processing_applied'] = True
                        current_input = result['output_file']
                        temp_files.append(current_input)
                        applied_methods.append('de_reverb')
                        logger.info('   ✅ De-reverb thành công')
                    else:
                        logger.info(f"   ⚠️ De-reverb thất bại: {result['message']}")
                elif method == 'de_essing_only':
                    logger.info('   🔧 Xử lý de-essing...')
                    result = apply_de_essing(current_input)
                    if result['success']:
                        processing_info['de_essing'] = True
                        processing_info['processing_applied'] = True
                        current_input = result['output_file']
                        temp_files.append(current_input)
                        applied_methods.append('de_essing')
                        logger.info('   ✅ De-essing thành công')
                    else:
                        logger.info(f"   ⚠️ De-essing thất bại: {result['message']}")
                else:
                    logger.info(f'   ⚠️ Phương pháp không hợp lệ: {method}')
            if processing_info['processing_applied']:
                return {'success': True, 'output_file': current_input, 'message': f"✅ Xử lý audio hoàn thành với {len(applied_methods)} phương pháp: {', '.join(applied_methods)}", 'processing_info': processing_info, 'temp_files': temp_files}
            else:
                return {'success': False, 'output_file': None, 'message': '❌ Không có phương pháp xử lý nào thành công', 'processing_info': processing_info, 'temp_files': temp_files}
        elif processing_mode == 'auto':
            logger.info('🔧 Chế độ: Tự động kiểm tra chất lượng và quyết định xử lý...')
            from audio_analyze import analyze_audio
            logger.info('   🔍 Bước 1: Phân tích chất lượng audio...')
            audio_meta = analyze_audio(input_file)
            if audio_meta['ok']:
                logger.info('   ✅ Chất lượng audio đạt yêu cầu - bỏ qua xử lý')
                processing_info['processing_applied'] = False
                processing_info['skip_reason'] = 'Audio chất lượng tốt, không cần xử lý'
                return {'success': True, 'output_file': input_file, 'message': '✅ Audio chất lượng tốt, không cần xử lý', 'processing_info': processing_info}
            else:
                logger.info('   ⚠️ Chất lượng audio không đạt yêu cầu - tiến hành xử lý')
                logger.info('   📋 Các vấn đề phát hiện:')
                for warning in audio_meta.get('warnings', []):
                    logger.info(f'      - {warning}')
                logger.info('   🔧 Bước 2: Áp dụng tất cả kỹ thuật cải thiện...')
                enhance_result = enhance_audio_quality(input_file, output_file)
                if enhance_result['success']:
                    processing_info['normalization'] = True
                    processing_info['noise_reduction'] = True
                    processing_info['silence_removal'] = True
                    processing_info['compression'] = True
                    processing_info['de_reverb'] = True
                    processing_info['de_essing'] = True
                    processing_info['enhance_quality'] = True
                    processing_info['processing_applied'] = True
                    processing_info['auto_processing_reason'] = f"Audio không đạt chất lượng: {', '.join(audio_meta.get('warnings', []))}"
                    logger.info('   ✅ Đã cải thiện chất lượng audio thành công')
                    return {'success': True, 'output_file': enhance_result['output_file'], 'message': f"✅ Đã cải thiện chất lượng audio (phát hiện {len(audio_meta.get('warnings', []))} vấn đề)", 'processing_info': processing_info, 'temp_files': [enhance_result['output_file']] if enhance_result['output_file'] != input_file else []}
                else:
                    logger.info(f"   ❌ Không thể cải thiện chất lượng: {enhance_result['message']}")
                    return {'success': False, 'output_file': None, 'message': f"❌ Không thể cải thiện chất lượng audio: {enhance_result['message']}", 'processing_info': processing_info}
        elif processing_mode == 'off':
            logger.info('🔧 Chế độ: Tắt xử lý audio...')
            return {'success': True, 'output_file': input_file, 'message': '✅ Không xử lý audio (chế độ tắt)', 'processing_info': processing_info}
        else:
            return {'success': False, 'output_file': None, 'message': f'❌ Chế độ xử lý không hợp lệ: {processing_mode}', 'processing_info': processing_info}
    except Exception as e:
        return {'success': False, 'output_file': None, 'message': f'❌ Lỗi khi xử lý audio: {str(e)}', 'processing_info': processing_info}