# Hướng dẫn Bàn Giao: STT-Nova2

Tài liệu này hướng dẫn cách cài đặt, chạy dự án và chứa các thông tin tài khoản quan trọng cho người tiếp nhận.

## 1. Cấu trúc Source Code
- Toàn bộ source logic nằm ở thư mục root và `src/`.
- File init database được gom vào thư mục `scripts/schema.sql`.
- File cấu hình mẫu: `.env.example` — copy thành `.env` và điền thông tin thực tế.

## 2. Thông tin Tài Khoản (Placeholder)
> **Lưu ý**: Hãy cập nhật lại file này hoặc file `.env` bằng các thông tin thực tế khi deploy ở môi trường mới.

- **PostgreSQL Database (External/Tổng đài)**
  - Host: `[THÔNG TIN BẢO MẬT]`
  - Port: `5432`
  - User: `[THÔNG TIN BẢO MẬT]`
  - Pass: `[THÔNG TIN BẢO MẬT]`
  - DB Name: `fusionpbx`

- **Vector DB (PgVector - Internal)**
  - Host: `[THÔNG TIN BẢO MẬT]`
  - Port: `5432`
  - User: `[THÔNG TIN BẢO MẬT]`
  - Pass: `[THÔNG TIN BẢO MẬT]`
  - DB Name: `vector_db`

- **API Keys**
  - Deepgram API Key: `[THÔNG TIN BẢO MẬT]`
  - Google Gemini API Key: `[THÔNG TIN BẢO MẬT]`
  - Groq API Key: `[THÔNG TIN BẢO MẬT]`
  - Telegram Bot Token: `[THÔNG TIN BẢO MẬT]`

## 3. Hướng dẫn Deploy

### 3.1. Chạy qua Docker (Khuyến nghị)
Sử dụng Docker Compose để build và chạy tất cả dịch vụ.
```bash
# 1. Copy file biến môi trường mẫu
cp .env.example .env

# 2. Chỉnh sửa .env để khớp với cấu hình hệ thống thực tế (điền các thông tin bảo mật ở trên)
nano .env

# 3. Khởi tạo schema database (nếu chưa có)
psql -U [USERNAME] -h [HOSTNAME] -d [DB_NAME] -f scripts/schema.sql

# 4. Khởi chạy Docker
docker-compose up -d --build
```

### 3.2. Chạy Local (Môi trường Dev)
1. Tạo virtual environment:
```bash
python3 -m venv venv
```
2. Kích hoạt venv và cài đặt thư viện:
```bash
source venv/bin/activate
pip install -r requirements.txt
```
3. Chạy file khởi tạo schema vào CSDL PostgreSQL của bạn:
```bash
psql -U [USERNAME] -h [HOSTNAME] -d [DB_NAME] -f scripts/schema.sql
```
4. Khởi chạy server FastAPI:
```bash
uvicorn api_server:app --host 0.0.0.0 --port 8123
```

## 4. Lưu ý quan trọng: Định dạng dòng (Line Endings)

> **⚠️ CẢNH BÁO**: Nếu bạn mở/chỉnh sửa file trên **Windows** rồi chuyển sang chạy trên **Ubuntu/Linux**, các file `.sh` và `.sql` có thể bị dính ký tự `\r\n` (CRLF), gây lỗi `bad interpreter` hoặc `command not found`.

**Cách xử lý:**
```bash
# Cài đặt dos2unix (nếu chưa có)
sudo apt install dos2unix

# Chuyển đổi các file script về chuẩn LF
dos2unix *.sh scripts/*.sql docker-compose.yml Dockerfile
```

Tất cả file trong bản giao này đã được chuẩn hóa về LF. File `.gitattributes` cũng đã được cấu hình để tự động enforce LF khi commit.
