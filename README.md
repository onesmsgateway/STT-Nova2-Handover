# 🚀 STT-Nova2 Service

> **Speech-to-Text Service với AI Enhancement và Telegram Bot Integration**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-red?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)](https://telegram.org/)

## 🎯 Tính năng chính

- 🎵 **Speech-to-Text** với Deepgram Nova-2 (độ chính xác cao)
- 🔗 **URL-only Processing** - chỉ xử lý audio từ URL
- 🎛️ **6 Audio Processing Modes** tối ưu cho từng loại audio
- 🔄 **Queue Management** xử lý batch requests
- 🛡️ **Duplicate Prevention** tránh retry storm và resource waste
- 🤖 **Telegram Bot** thông báo real-time và điều khiển từ xa
- 📝 **AI Summarization** với Google Gemini
- 🐳 **Docker Ready** với health checks
- 📊 **Real-time Monitoring** và status tracking

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone <repository-url>
cd STT-Nova2
```

### 2. Cấu hình (Tùy chọn)
```bash
# Copy config template
cp config_template.py config.py

# Chỉnh sửa config.py với API keys của bạn
# - DEEPGRAM_API_KEYS
# - GOOGLE_API_KEYS  
# - TELEGRAM_BOT_TOKEN (tùy chọn)
```

### 3. Chạy với Docker Compose
```bash
# Start service
docker-compose up -d

# Kiểm tra logs
docker-compose logs -f stt-nova2

# Kiểm tra health
curl http://localhost:8000/
```

### 4. Test API
```bash
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["https://example.com/audio.wav"],
    "audio_processing_mode": "enhance_all",
    "max_words": 150
  }'
```

## 📋 API Endpoints

### Core STT/Audio
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/` | GET | Health check |
| `/process` | POST | Xử lý batch audio URLs |
| `/webhook` | POST | Webhook cho CDR system |
| `/v1/tasks/{task_id}` | GET | Poll kết quả xử lý |
| `/queue/status` | GET | Trạng thái queue |

### TTS (Text-to-Speech)
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/v1/tts/speak` | POST | Edge TTS (Microsoft, miễn phí) |
| `/v1/tts/clone` | POST | VieNeu-TTS (Voice Cloning) |
| `/v1/tts/voices` | GET | Danh sách voices |

### AI Hub
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/v1/ai-hub/vectorize` | POST | Upload file để vectorize (PDF, Image, Audio) |
| `/v1/ai-hub/tasks/{task_id}` | GET | Tiến độ xử lý AI Hub |
| `/v1/docs/parse` | POST | Trích xuất text từ PDF/Docx |

📖 **Chi tiết AI Hub**: [docs/AI_HUB_API.md](docs/AI_HUB_API.md) - Webhook response, domain mapping, stateless retry

### Chatbot (RAG)
| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/v1/chat` | POST | Chat với RAG knowledge base |
| `/v1/prompts` | GET | Lấy system prompts |

📖 **Xem chi tiết**: [DEMO_GUIDE.md](docs/DEMO_GUIDE.md) | [Postman Collection](docs/STT-Nova2.postman_collection.json)

## 🛡️ Duplicate Prevention System

### Vấn đề được giải quyết
- **Retry Storm**: Client retry nhiều lần khi xử lý lâu (2-3 phút)
- **Resource Waste**: CPU/RAM quá tải do xử lý cùng 1 file audio nhiều lần
- **Performance Impact**: 5-6 lần retry chỉ để xử lý 1 file audio

### Cách hoạt động
1. **Queue-Based Check**: Kiểm tra URL trong queue và đang xử lý
2. **Duplicate Prevention**: Skip duplicates trước khi add vào queue
3. **Sequential Processing**: Xử lý tuần tự từng file audio
4. **Smart Response**: Return appropriate status cho duplicates

### Monitoring
```bash
# Kiểm tra trạng thái queue
curl http://localhost:8000/queue/status

# Bắt đầu xử lý queue
curl -X POST http://localhost:8000/queue/start
```

### Response cho Duplicate Requests
```json
HTTP 429 Too Many Requests
{
  "detail": "Request đang được xử lý"
}
```

### Response cho Queued Requests
```json
{
  "status": "queued",
  "queue_info": {
    "total_in_queue": 5,
    "added_count": 1
  }
}
```

📖 **Chi tiết**: Xem [DUPLICATE_PREVENTION_GUIDE.md](DUPLICATE_PREVENTION_GUIDE.md)

## 🔗 Webhook Integration

### CDR System Webhook

**Endpoint:** `POST /webhook`

**Mục đích:** Nhận dữ liệu từ CDR system và xử lý audio tự động

### Request Format

```json
{
  "recording_url": "https://conek-pbx.conek.vn/app/xml_cdr/download.php?id=a44638e3-5a15-458f-920c-5b75dac4a8e7",
  "xml_cdr_uuid": "9acc2e32-5b32-4617-abde-180719eaf9c9",
  "direction": "outbound",
  "billsec": 37,
  "caller_id": "0123456789",
  "callee_id": "0987654321",
  "start_time": "2025-01-05 10:30:00",
  "end_time": "2025-01-05 10:30:37"
}
```

### Validation Logic

**✅ Sẽ xử lý khi:**
- `direction = "outbound"`
- `billsec > 10` (giây)

**⏭️ Sẽ skip khi:**
- `direction != "outbound"`
- `billsec <= 10` (giây)

### Response Format

**Khi xử lý thành công:**
```json
{
  "request_id": "dee918ec-9e46-411f-9601-7a420aa3df30",
  "xml_cdr_uuid": "9acc2e32-5b32-4617-abde-180719eaf9c9",
  "status": "completed",
  "recording_url": "https://conek-pbx.conek.vn/app/xml_cdr/download.php?id=a44638e3-5a15-458f-920c-5b75dac4a8e7",
  "direction": "outbound",
  "billsec": 37,
  "transcript": "Nội dung transcript...",
  "summary": "Tóm tắt cuộc gọi...",
  "transcript_length": 1680,
  "summary_length": 713,
  "error": null,
  "processing_time": 45.2,
  "timestamp": "2025-01-05T10:30:45.123456"
}
```

**Khi skip:**
```json
{
  "request_id": "429a5477-f35b-4332-9a06-209c209fc228",
  "xml_cdr_uuid": "inbound-uuid-123",
  "status": "skipped",
  "recording_url": "https://example.com/audio.wav",
  "direction": "inbound",
  "billsec": 45,
  "skip_reason": "Direction không phải outbound: inbound",
  "transcript": "",
  "summary": "",
  "transcript_length": 0,
  "summary_length": 0,
  "error": null,
  "processing_time": 0.1,
  "timestamp": "2025-01-05T10:30:45.123456"
}
```

### Test Webhook

```bash
# Test với curl
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "recording_url": "https://example.com/audio.wav",
    "xml_cdr_uuid": "test-uuid-123",
    "direction": "outbound",
    "billsec": 30
  }'
```

## ⚙️ Audio Processing Modes

| Mode | Mô tả | Use Case |
|------|-------|----------|
| `auto` | Tự động phát hiện và xử lý dựa trên chất lượng audio | **Mặc định**, phù hợp hầu hết trường hợp |
| `off` | Không tiền xử lý, gửi thẳng audio gốc | Audio chất lượng cao sẵn |
| `enhance_all` | Giảm nhiễu + tăng cường giọng nói | Audio nhiễu nhiều, cần chất lượng tốt nhất |
| `enhance_speech` | Chỉ tăng cường giọng nói | Giọng nói nhỏ, cần làm rõ |
| `normal` | Giảm nhiễu nhẹ, giữ nguyên âm lượng | Audio tương đối tốt |
| `aggressive` | Giảm nhiễu mạnh | Audio rất nhiễu |
| `conservative` | Giảm nhiễu nhẹ nhàng | Tinh chỉnh nhẹ |

## 📊 call_topic (Classification)

`call_topic` là kết quả phân loại chủ đề cuộc gọi dựa trên nội dung transcript, sử dụng **Google Gemini AI**.

### Các loại chủ đề
| Giá trị | Mô tả |
|---------|-------|
| `Tư vấn dịch vụ` | Khách hàng hỏi về sản phẩm/dịch vụ |
| `Hỗ trợ kỹ thuật` | Yêu cầu hỗ trợ về kỹ thuật |
| `Khiếu nại/Phản hồi` | Khách phản ánh vấn đề |
| `Đặt lịch hẹn` | Đặt lịch, hẹn gặp |
| `Thông tin chung` | Hỏi thông tin chung |
| `N/A` | Không xác định được chủ đề |

## 🤖 Telegram Bot

### Commands
- `/start` - Khởi động bot
- `/status` - Kiểm tra trạng thái service
- `/restart` - Hướng dẫn restart
- `/help` - Hướng dẫn sử dụng

### Notifications
- 🚀 Startup notifications
- ⚠️ Error alerts
- 🔄 Processing updates
- 📊 System monitoring

## 🐳 Docker Commands

```bash
# Build image
docker build -t stt-nova2:latest .

# Run container
docker run -d --name stt-nova2-service -p 8000:8000 stt-nova2:latest

# View logs
docker logs -f stt-nova2-service

# Stop service
docker stop stt-nova2-service

# Remove container
docker rm -f stt-nova2-service
```

## 📁 Project Structure

```
STT-Nova2/
├── api_server.py          # FastAPI server
├── telegram_bot.py        # Telegram bot logic
├── telegram_handler.py    # Command handler
├── audio_processor.py     # Audio processing core
├── queue_manager.py       # Queue management
├── summarizer.py          # AI summarization
├── config.py             # Configuration
├── requirements.txt      # Dependencies
├── Dockerfile           # Docker image
├── docker-compose.yml   # Docker Compose
├── resource/            # Audio files
├── queue_data/          # Queue persistence
└── docs/               # Documentation
```

## 🔧 Configuration

### Environment Variables
```python
# API Keys
DEEPGRAM_API_KEYS = ['your_deepgram_key']
GOOGLE_API_KEYS = ['your_google_key']

# Telegram Bot (tùy chọn)
TELEGRAM_BOT_TOKEN = 'your_bot_token'
TELEGRAM_ADMIN_CHAT_ID = your_chat_id
TELEGRAM_BOT_ENABLED = True

# Service Settings
MAX_CONCURRENT_REQUESTS = 3
QUEUE_TIMEOUT = 300
```

## 📊 Performance

- **Processing Speed**: ~2-3 phút cho 100 URLs
- **Memory Usage**: ~500MB cho 100 URLs
- **Concurrent Requests**: 3 requests đồng thời
- **Queue Persistence**: Không mất dữ liệu khi restart

## 🚨 Troubleshooting

### Common Issues

1. **Docker không start**
   ```bash
   # Kiểm tra Docker daemon
   docker ps
   
   # Restart Docker Desktop
   open -a Docker
   ```

2. **Port 8000 đã được sử dụng**
   ```bash
   # Thay đổi port trong docker-compose.yml
   ports:
     - "8001:8000"
   ```

3. **Telegram Bot không hoạt động**
   - Kiểm tra Bot Token và Chat ID
   - Kiểm tra bot permissions trong group

### Health Checks
```bash
# Service health
curl http://localhost:8000/

# Container health
docker inspect stt-nova2-service | grep Health -A 10

# Logs
docker logs stt-nova2-service
```

## 📚 Documentation

- 📖 **[SERVICE_README.md](SERVICE_README.md)** - Chi tiết API và deployment
- 🔄 **[WORKFLOW.md](WORKFLOW.md)** - Workflow và best practices
- 🐳 **[DOCKER_README.md](DOCKER_README.md)** - Docker deployment guide
- ⚙️ **[setup_pycharm.md](setup_pycharm.md)** - Development setup

## 🤝 Contributing

1. Fork repository
2. Tạo feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Tạo Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📞 Support

- 📧 **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- 💬 **Telegram**: Sử dụng bot commands
- 📖 **Documentation**: Xem docs/ folder

---

**STT-Nova2 Service** - Powered by Deepgram & Google AI 🤖
