# Data Flow: STT-Nova2

## 1. Luồng xử lý Voice/Audio (Speech-To-Text & Summarize)

1. **Tiếp nhận yêu cầu**: 
   - Audio được tải lên qua API hoặc cung cấp dưới dạng URL (thông qua webhook từ tổng đài).
2. **Tiền xử lý âm thanh**:
   - Audio được kiểm tra độ dài, format. Nếu cần sẽ qua module Enhance để cải thiện âm thanh hoặc cắt đoạn tĩnh (`audio_processor.py`).
3. **Speech to Text**:
   - Module STT gọi tới Deepgram (nếu có API) hoặc model PhoWhisper local để trích xuất văn bản từ âm thanh.
4. **Phân tích và Tóm tắt**:
   - Văn bản nhận được (Transcript) được gửi cho LLM (Gemini) để phân loại Topic và tóm tắt ngắn gọn.
5. **Lưu trữ kết quả**:
   - `DatabaseManager` sẽ gọi `UPDATE` vào bảng `cdr` trong CSDL của tổng đài để lưu lại kết quả Transcript và Summary dựa theo `cdr_uuid`.
   - Bắn thông báo qua Webhook (nếu được cấu hình).

## 2. Luồng xử lý Vector Database

1. **Khởi tạo dữ liệu**:
   - File/văn bản được đẩy lên API, chia thành các text chunk nhỏ.
2. **Vector hoá**:
   - Chạy qua Gemini embeddings API để lấy vector (768 chiều).
3. **Lưu vào CSDL**:
   - `VectorStore` lưu vector vào bảng `resource_vectors` theo schema riêng của Tenant (được xác định dựa vào `school_code`).
4. **Tìm kiếm (Semantic Search)**:
   - Query được chuyển thành vector và query cosine similarity `1 - (embedding <=> query)` trong DB Postgres.
5. **Cờ vi phạm (Flagged Content)**:
   - Trong quá trình trò chuyện/tìm kiếm, nếu phát hiện nội dung có vi phạm tiêu chuẩn, hệ thống log nội dung vào bảng `public.flagged_content`.

## 3. Luồng Quản lý Lỗi & Thông báo
- Bất kỳ lỗi sinh ra trong Worker hoặc Server đều được ghi vào log và đẩy Notification lên kênh Telegram Admin thông qua `telegram_bot.py`.
