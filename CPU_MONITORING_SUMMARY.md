# 🚨 CPU Monitoring & Fallback - Tóm tắt

## ✅ Đã hoàn thành

### 1. **CPU & RAM Monitoring System**
- ✅ Tích hợp vào `audio_processor.py`
- ✅ **Background monitoring thread** trong quá trình PhoWhisper chạy
- ✅ Ngưỡng CPU: 85% (có thể tùy chỉnh)
- ✅ Ngưỡng RAM: 85% (có thể tùy chỉnh)
- ✅ Grace period: 5 giây trước khi force cancel
- ✅ Sử dụng `psutil` để monitor system

### 2. **Telegram Integration**
- ✅ Gửi cảnh báo khi CPU > 85% HOẶC RAM > 85% trong quá trình PhoWhisper chạy
- ✅ Hiển thị thông tin chi tiết (CPU, RAM, Audio URL)
- ✅ Grace period 5 giây trước khi force cancel
- ✅ Thông báo rõ ràng khi fallback sang Deepgram

### 3. **Fallback Mechanism**
- ✅ **Force cancel PhoWhisper** khi CPU > 85% HOẶC RAM > 85% trong 5+ giây
- ✅ Tự động chuyển sang Deepgram
- ✅ Thông báo rõ ràng khi fallback
- ✅ Engine tracking (`phowhisper` vs `deepgram_fallback`)
- ✅ Fallback reason tracking

### 4. **Error Handling**
- ✅ Graceful fallback khi Telegram lỗi
- ✅ Timeout protection
- ✅ Comprehensive logging
- ✅ Skip audio nếu user từ chối

## 🔧 Files đã thay đổi

### `audio_processor.py`
- ➕ Import `psutil` và `time`
- ➕ CPU monitoring methods
- ➕ Telegram notification system
- ➕ Fallback logic trong `_perform_stt()`
- ➕ User response handling

### `api_server.py`
- ➕ Set Telegram bot cho AudioProcessor
- ➕ Integration với existing Telegram system

### `requirements.txt`
- ✅ `psutil>=5.9.0` đã có sẵn

## 🎯 Cách sử dụng

### 1. **Automatic (Default)**
```python
# Không cần config gì thêm
# Hệ thống tự động check CPU khi chạy PhoWhisper
```

### 2. **Custom CPU Threshold**
```python
processor.cpu_threshold = 90.0  # 90% thay vì 85%
```

### 3. **Telegram Commands**
- `YES` / `FALLBACK` / `OK` → Chuyển sang Deepgram
- `NO` / `REJECT` / `CANCEL` → Từ chối và bỏ qua

## 📊 Flow Diagram (Updated Logic)

```
PhoWhisper Request
        ↓
Start PhoWhisper Process
        ↓
Start CPU & RAM Monitoring Thread
        ↓
PhoWhisper Running + Resource Monitoring
        ↓
CPU > 85% OR RAM > 85% for 5+ seconds?
   ↙        ↘
  No         Yes
   ↓          ↓
PhoWhisper   Send Telegram Alert
Completes       ↓
   ↓        Grace Period (5s)
Return Result   ↓
            Still High Resource?
               ↙    ↘
             No     Yes
              ↓      ↓
         Continue   Force Cancel PhoWhisper
         PhoWhisper      ↓
              ↓      Fallback to Deepgram
         Return Result   ↓
                    Return Result
```

## 🚀 Benefits

1. **🛡️ Server Protection**: Tránh CPU và RAM overload
2. **🔄 Smart Fallback**: Tự động chuyển sang Deepgram
3. **👤 User Control**: Quyết định qua Telegram
4. **📱 Real-time Alerts**: Thông báo ngay lập tức
5. **🔍 Transparent**: Logs chi tiết cho monitoring

## 🧪 Testing

### Test CPU Check:
```bash
# Set threshold thấp để trigger
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/audio.wav"],
    "engine": "phowhisper"
  }'
```

### Monitor Logs:
```bash
docker-compose logs -f stt-nova2-service | grep -E "(CPU|fallback|PhoWhisper)"
```

## 📝 Example Logs

```
🔍 Checking CPU trước khi chạy PhoWhisper...
⚠️ CPU quá cao: 92.3% (threshold: 85%)
📱 Đã gửi CPU high alert cho https://example.com/audio.wav
🔄 CPU cao (92.3%), fallback sang Deepgram...
✅ FALLBACK SANG DEEPGRAM
🎵 Audio: https://example.com/audio.wav
🔄 Đang chuyển sang Deepgram...
```

## 🎉 Kết quả

- ✅ **Server được bảo vệ** khỏi CPU overload
- ✅ **User có control** qua Telegram
- ✅ **Fallback tự động** sang Deepgram
- ✅ **Zero downtime** cho service
- ✅ **Transparent monitoring** với logs chi tiết

---

**🎯 Tính năng đã sẵn sàng sử dụng!** Chỉ cần deploy và test với audio thật.
