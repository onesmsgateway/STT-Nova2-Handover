# Architecture Overview: STT-Nova2

## 1. Tổng quan
Dự án **STT-Nova2** là một hệ thống cung cấp các dịch vụ liên quan đến xử lý âm thanh (Speech-to-Text), phân tích cuộc gọi, và trích xuất thông tin (summarization/classification) sử dụng các mô hình AI.

## 2. Thành phần hệ thống

### 2.1. API Server (`api_server.py`)
- Framework: FastAPI
- Cung cấp các endpoint để tiếp nhận file audio, URL audio hoặc các task xử lý văn bản.
- Giao tiếp với các queue và quản lý workers xử lý bất đồng bộ.

### 2.2. Audio Processing (`stt_service.py`, `phowhisper_engine.py`)
- Xử lý các tác vụ Speech-to-Text.
- Hỗ trợ xử lý thông qua Deepgram API hoặc model local PhoWhisper tùy thuộc vào cấu hình môi trường.
- Hỗ trợ cắt, chia nhỏ audio và nâng cao chất lượng trước khi nhận diện (`audio_processor.py`, `audio_enhanced.py`).

### 2.3. LLM Processing (`summarizer.py`, `text_classifier.py`)
- Sử dụng Google AI (Gemini) để thực hiện tóm tắt nội dung văn bản (summarization) và phân loại cuộc gọi.
- Hỗ trợ vector hoá (embeddings) để lưu vào Vector DB phục vụ tìm kiếm ngữ nghĩa.

### 2.4. Data Storage & Integration
- **PostgreSQL Database** (`database.py`): Kết nối với cơ sở dữ liệu của tổng đài để cập nhật `transcript`, `summary`, và `call_topic` vào bảng `cdr`.
- **Vector Database** (`src/chatbot/vector_store.py`): Quản lý vector ngữ nghĩa của file, phân chia dữ liệu dựa theo schema tenant (tenant isolation). Bảng `flagged_content` dùng lưu các nội dung vi phạm moderation.

### 2.5. Worker & Queue (`queue_manager.py`)
- Chạy dưới nền để polling các url/file.
- Xử lý tuần tự các task tránh quá tải server.

### 2.6. Telegram Bot (`telegram_bot.py`, `telegram_handler.py`)
- Bot thông báo, log lỗi hệ thống và có thể tương tác tra cứu/giám sát hệ thống qua Telegram chat.
