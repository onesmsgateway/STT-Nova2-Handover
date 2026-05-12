# 🚀 STT-Nova2 Demo Guide

> Hướng dẫn từng bước để test API STT-Nova2

## 📋 Mục lục
1. [Yêu cầu](#yêu-cầu)
2. [STT - Speech-to-Text](#stt---speech-to-text)
3. [TTS - Text-to-Speech](#tts---text-to-speech)
4. [AI Hub Vectorization](#ai-hub-vectorization)
5. [Xử lý lỗi](#xử-lý-lỗi)

---

## 📌 Yêu cầu

- **Base URL:** `https://stt.minhbv.com` (hoặc `http://localhost:8000` nếu local)
- **Tool test:** Postman, curl, hoặc bất kỳ HTTP client
- **Import Postman Collection:** [STT-Nova2.postman_collection.json](./STT-Nova2.postman_collection.json)

---

## 🎙️ STT - Speech-to-Text

### Bước 1: Gửi Audio URL

```bash
curl -X POST "https://stt.minhbv.com/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "recording_url": "https://your-server.com/audio.wav",
    "xml_cdr_uuid": "unique-id-123",
    "direction": "outbound",
    "billsec": 37,
    "duration": 45
  }'
```

**Response:**
```json
{
  "task_id": "abc123-def456",
  "status": "queued",
  "message": "Request received and queued for processing"
}
```

### Bước 2: Poll Kết quả

```bash
curl "https://stt.minhbv.com/v1/tasks/abc123-def456"
```

**Response (completed):**
```json
{
  "status": "completed",
  "result": {
    "transcript": "Xin chào, tôi muốn tư vấn dịch vụ...",
    "summary": "Khách hàng gọi để tư vấn về dịch vụ internet...",
    "call_topic": "Tư vấn dịch vụ"
  }
}
```

### 📊 Giải thích Response Fields

| Field | Mô tả |
|-------|-------|
| `transcript` | Toàn bộ nội dung đã được chuyển thành văn bản |
| `summary` | Bản tóm tắt ngắn gọn của cuộc hội thoại |
| `call_topic` | Phân loại chủ đề: Tư vấn dịch vụ, Hỗ trợ kỹ thuật, Khiếu nại, Đặt lịch, Thông tin chung, N/A |

### ⚙️ Audio Processing Modes

| Mode | Mô tả |
|------|-------|
| `auto` | Tự động phát hiện và xử lý (mặc định) |
| `off` | Không tiền xử lý audio |
| `enhance_all` | Giảm nhiễu + tăng giọng nói |
| `enhance_speech` | Chỉ tăng cường giọng nói |
| `normal` | Giảm nhiễu nhẹ |
| `aggressive` | Giảm nhiễu mạnh |
| `conservative` | Giảm nhiễu nhẹ nhàng |

---

## 🔊 TTS - Text-to-Speech

### Edge TTS (Miễn phí, nhanh)

```bash
curl -X POST "https://stt.minhbv.com/v1/tts/speak" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Xin chào, đây là bản tin thời tiết.",
    "voice": "vi-VN-HoaiMyNeural",
    "rate": "+0%",
    "provider": "edge"
  }' \
  --output audio.wav
```

### VieNeu-TTS (Chất lượng cao)

```bash
curl -X POST "https://stt.minhbv.com/v1/tts/clone" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Xin chào, đây là giọng nói VieNeu.",
    "voice": "Nguyên",
    "rate": "+0%",
    "return_json": true
  }'
```

### Danh sách Voices

| Provider | Voices |
|----------|--------|
| Edge TTS | `vi-VN-HoaiMyNeural` (Nữ), `vi-VN-NamMinhNeural` (Nam) |
| VieNeu | Nguyên, Tuyên, Sơn, Bình, Vĩnh (Nam) / Đoan, Dung, Ly, Ngọc, Hương (Nữ) |

---

## 📄 AI Hub Vectorization

Upload file để trích xuất text + tạo embeddings.

```bash
curl -X POST "https://stt.minhbv.com/v1/ai-hub/vectorize" \
  -F "file=@document.pdf" \
  -F "webhook_url=https://your-server.com/webhook" \
  -F "enable_summary=true"
```

**Hỗ trợ:**
- 📄 PDF, Docx
- 🖼️ Image (OCR với Gemini Vision)
- 🎵 Audio/Video (STT với PhoWhisper)

---

## ❌ Xử lý lỗi

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| `400 Bad Request` | Thiếu field bắt buộc | Kiểm tra `recording_url`, `xml_cdr_uuid` |
| `404 Not Found` | Endpoint không tồn tại | Kiểm tra URL |
| `status: skipped` | `direction != outbound` hoặc `billsec <= 10` | Chỉ xử lý cuộc gọi outbound > 10s |
| CORS Error | Gọi từ browser | Dùng Postman hoặc curl |

---

**Happy Testing! 🎉**
