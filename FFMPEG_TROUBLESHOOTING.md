# FFmpeg Troubleshooting Guide

## 🔍 Vấn đề: Audio Processing Fail với "❌ Không thể tải file audio từ URL"

### Root Cause Analysis

**Vấn đề**: Production container thiếu ffmpeg binary mặc dù Dockerfile có cài đặt.

**Triệu chứng**:
```
stt-nova2-service  | INFO:queue_manager:Xử lý URL: https://conek-pbx.conek.vn/app/xml_cdr/download.php?id=xxx
stt-nova2-service  | INFO:stats_manager:Đã cập nhật stats: +1 failed
```

**Nguyên nhân có thể**:
1. Container cũ chưa được rebuild
2. Build process bị lỗi
3. Base image có vấn đề
4. Package installation failed

## 🛠️ Solutions

### 1. Immediate Fix (Đã implement)
- ✅ **Fallback mechanism**: FFmpeg → Curl
- ✅ **Better error handling**
- ✅ **Improved logging**

### 2. Long-term Fix
- 🔧 **Rebuild container** với code mới
- 🔧 **Verify ffmpeg installation**

## 📋 Troubleshooting Steps

### Step 1: Check Current Container
```bash
# Check if ffmpeg is available
docker exec -it stt-nova2-service bash -c './check_ffmpeg.sh'
```

### Step 2: Rebuild Container
```bash
# Rebuild with new code
./rebuild_container.sh
```

### Step 3: Verify Fix
```bash
# Check container logs
docker-compose logs -f stt-nova2-service

# Test audio processing
curl -X POST http://localhost/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "recording_url": "https://conek-pbx.conek.vn/app/xml_cdr/download.php?id=test",
    "xml_cdr_uuid": "test-uuid",
    "direction": "outbound",
    "billsec": 41,
    "duration": 51
  }'
```

## 🔧 Expected Logs After Fix

**With FFmpeg**:
```
INFO:audio_processor:✅ Đã tải file thành công bằng ffmpeg: resource/downloaded_audio.wav
```

**With Curl Fallback**:
```
WARNING:audio_processor:⚠️ FFmpeg không được cài đặt, sẽ thử curl
INFO:audio_processor:🔄 FFmpeg thất bại, thử curl...
INFO:audio_processor:✅ Đã tải file thành công bằng curl: resource/downloaded_audio.wav
```

## 📊 Dockerfile Analysis

**Current Dockerfile** (should work):
```dockerfile
RUN apt-get update && apt-get install -y \
    ffmpeg \
    sox \
    libsox-fmt-all \
    file \
    curl \
    && rm -rf /var/lib/apt/lists/*
```

**Verification**:
- ✅ FFmpeg is listed in apt-get install
- ✅ Curl is also installed as fallback
- ✅ No .dockerignore issues

## 🚀 Deployment Checklist

- [ ] Code merged to main branch
- [ ] Container rebuilt with `./rebuild_container.sh`
- [ ] FFmpeg availability verified with `./check_ffmpeg.sh`
- [ ] Audio processing tested with real URL
- [ ] Logs monitored for success/failure

## 📈 Performance Impact

**FFmpeg vs Curl**:
- **FFmpeg**: Chuẩn hóa format (16kHz mono) - tốt hơn cho STT
- **Curl**: Download raw file - vẫn hoạt động nhưng có thể ảnh hưởng chất lượng

**Recommendation**: Cài đặt ffmpeg trên production để có chất lượng tốt nhất.
