# Hướng dẫn Bàn Giao: STT-Nova2

Tài liệu này hướng dẫn cách cài đặt, chạy dự án và chứa các thông tin tài khoản quan trọng cho người tiếp nhận.

## 1. Cấu trúc Source Code
- Toàn bộ source logic nằm ở thư mục root và `src/`.
- File init database được gom vào thư mục `scripts/schema.sql`.
- (Ghi chú: Tất cả comments và docstring đã được làm sạch theo tiêu chuẩn dự án bàn giao để giữ mã nguồn gọn gàng nhất).

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
  - Telegram Bot Token: `[THÔNG TIN BẢO MẬT]`

## 3. Hướng dẫn Deploy

### 3.1. Chạy qua Docker (Khuyến nghị)
Sử dụng Docker Compose để build và chạy tất cả dịch vụ.
```bash
# 1. Copy file biến môi trường mẫu
cp .env.example .env

# 2. Chỉnh sửa .env để khớp với cấu hình hệ thống thực tế (điền các thông tin bảo mật ở trên)
nano .env

# 3. Khởi chạy Docker
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
uvicorn api_server:app --host 0.0.0.0 --port 8000
```
