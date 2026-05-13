# 🚀 Hướng dẫn Deployment STT-Nova2 lên Server Ubuntu

Tài liệu này hướng dẫn chi tiết cách triển khai hệ thống **STT-Nova2** trên môi trường Ubuntu sử dụng Docker.

---

## 📋 1. Yêu cầu hệ thống (Minimum Requirements)

Để hệ thống chạy ổn định (đặc biệt là các model AI xử lý audio), server cần đáp ứng:

- **OS**: Ubuntu 22.04 LTS hoặc mới hơn.
- **CPU**: Tối thiểu 4 Cores (Khuyến nghị 6-8 Cores).
- **RAM**: Tối thiểu 8GB (Khuyến nghị 16GB).
- **Disk**: 20GB dung lượng trống (để chứa Docker images và AI Models).
- **Network**: Kết nối internet ổn định để download các model (~2GB).

---

## 🛠️ 2. Cài đặt các thành phần cần thiết

Chạy các lệnh sau để cài đặt Docker và Git trên server Ubuntu:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Cài đặt các công cụ cơ bản
sudo apt install -y git curl wget build-essential

# Cài đặt Docker (nếu chưa có)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Cài đặt Docker Compose (Plugin)
sudo apt install -y docker-compose-plugin
```

---

## 📥 3. Clone source code và Cấu hình

### 3.1. Clone Repository
```bash
git clone <URL_REPOSITORY_CUA_BAN>
cd STT-Nova2
```

### 3.2. Cấu hình Environment (.env)
Copy file mẫu và chỉnh sửa các thông số API Keys:

```bash
cp .env.example .env
nano .env
```

**Các thông số quan trọng cần lưu ý:**
- `DEEPGRAM_API_KEYS`: Key xử lý Speech-to-Text.
- `GOOGLE_API_KEYS`: Key cho Gemini AI (Summarization).
- `TELEGRAM_BOT_TOKEN`: Token của bot thông báo.
- `POSTGRESQL_HOST`: Địa chỉ Database (nếu dùng DB ngoài).

---

## 🚀 4. Triển khai (Deployment)

Chúng ta sử dụng script `deploy.sh` đã được tối ưu hóa để triển khai tự động trong 1 bước.

### 4.1. Phân quyền thực thi
```bash
chmod +x deploy.sh
chmod +x scripts/*.sh
chmod +x *.sh
```

### 4.2. Chạy script Deployment
Script này sẽ tự động:
1. Download các AI Models nặng (~1.8GB).
2. Clone các thư viện bổ trợ.
3. Build Docker Image.
4. Khởi chạy container.

```bash
./deploy.sh
```

> [!IMPORTANT]
> Quá trình download model lần đầu có thể mất 5-10 phút tùy vào tốc độ mạng của server.

---

## 🔍 5. Kiểm tra trạng thái

Sau khi chạy xong, kiểm tra container có đang chạy không:

```bash
docker ps
```

Kiểm tra Logs để đảm bảo không có lỗi khởi động:
```bash
docker logs -f stt-nova2
```

Kiểm tra Health-check API:
```bash
curl http://localhost:8000/
```

---

## 🛠️ 6. Các lệnh quản lý thường dùng

| Thao tác | Lệnh |
|----------|------|
| **Xem Logs** | `docker logs -f stt-nova2` |
| **Restart Service** | `docker restart stt-nova2` |
| **Cập nhật code mới** | `./deploy.sh` (Script này tự động pull git và rebuild) |
| **Dừng hệ thống** | `docker compose down` |
| **Kiểm tra FFmpeg** | `./check_ffmpeg.sh` |

---

## 🚨 7. Xử lý sự cố thường gặp (Troubleshooting)

### 7.1. Lỗi thiếu FFmpeg
Mặc dù Docker đã cài sẵn, nhưng nếu bạn chạy trực tiếp trên host và gặp lỗi audio, hãy cài thêm:
```bash
sudo apt install -y ffmpeg
```

### 7.2. Hết dung lượng Disk
Docker build có thể chiếm nhiều bộ nhớ đệm. Hãy dọn dẹp bằng:
```bash
docker system prune -a
```

### 7.3. Không kết nối được Database
Nếu Database PostgreSQL chạy trên cùng host nhưng ngoài Docker, hãy đảm bảo `POSTGRESQL_HOST` trong `.env` là địa chỉ IP của host hoặc sử dụng `host.docker.internal`.

### 7.4. RAM bị tràn (OOM)
Nếu server bị treo khi xử lý audio dài, hãy kiểm tra giới hạn tài nguyên trong `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 8G # Tăng lên nếu cần
```

---

## 📞 Hỗ trợ
Nếu gặp vấn đề trong quá trình deploy, hãy kiểm tra file `FFMPEG_TROUBLESHOOTING.md` hoặc `DUPLICATE_PREVENTION_GUIDE.md` trong thư mục gốc.
