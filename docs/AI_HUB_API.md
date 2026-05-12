# AI Hub API Documentation

## Overview

AI Hub Service cung cấp REST API để xử lý file đa phương tiện (PDF, Image, Audio, Video) thành vectors cho RAG (Retrieval Augmented Generation). Service hoạt động theo mô hình **stateless** - không lưu trữ file hay chunks, chỉ xử lý và trả kết quả qua webhook.

---

## API Endpoints

### 1. Upload File để Vectorize

**Endpoint:** `POST /v1/ai-hub/vectorize`

**Content-Type:** `multipart/form-data`

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | ✅ | File cần xử lý (PDF, Image, Audio, Video) |
| `webhook_url` | string | ✅ | URL nhận kết quả sau khi xử lý xong |
| `enable_summary` | boolean | ❌ | Tạo summary (default: false) |
| `enable_classification` | boolean | ❌ | Phân loại nội dung (default: false) |
| `metadata` | JSON | ❌ | Metadata tùy chỉnh |

**Example Request:**

```bash
curl -X POST "https://stt.minhbv.com/v1/ai-hub/vectorize" \
  -F "file=@document.pdf" \
  -F "webhook_url=https://thuvien.one.edu.vn/api/webhook/ai_hub_result" \
  -F "enable_summary=true" \
  -F "metadata={\"school_id\":\"abc123\",\"uploader\":\"admin\"}"
```

**Response (200 OK):**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "File đang được xử lý. Kết quả sẽ gửi về webhook_url"
}
```

---

### 2. Kiểm tra tiến độ xử lý

**Endpoint:** `GET /v1/ai-hub/tasks/{task_id}`

**Response (200 OK):**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45,
  "created_at": "2026-01-27T10:00:00Z",
  "updated_at": "2026-01-27T10:01:23Z"
}
```

**Status Values:**
- `queued`: Đang chờ xử lý
- `processing`: Đang xử lý (progress: 0-100)
- `completed`: Hoàn thành 100%
- `partial_success`: Hoàn thành một phần (một số chunks fail)
- `failed`: Thất bại hoàn toàn

---

### 3. Kiểm tra Readiness trước khi Upload

**Endpoint:** `GET /v1/ai-hub/readiness`

Caller services nên gọi endpoint này **TRƯỚC** khi upload file để:
- Kiểm tra quota API còn bao nhiêu
- Xác định có nên gửi request hay dừng lại
- Tránh spam khi service đang unavailable

**Response (200 OK - Service Ready):**

```json
{
  "ready": true,
  "accepting_requests": true,
  "status": "accepting",
  "reason": null,
  "quota_available": 6,
  "quota_total": 6,
  "retry_after": null,
  "timestamp": "2026-01-28T14:00:00+00:00"
}
```

**Response (503 Service Unavailable):**

```json
{
  "ready": false,
  "accepting_requests": false,
  "status": "unavailable",
  "reason": "Hết quota API, vui lòng thử lại sau",
  "quota_available": 0,
  "quota_total": 6,
  "retry_after": 60,
  "timestamp": "2026-01-28T14:00:00+00:00"
}
```

**Response Fields:**
| Field | Type | Mô tả |
|-------|------|-------|
| `ready` | boolean | Có thể gửi request không |
| `status` | string | `accepting` / `degraded` / `unavailable` |
| `reason` | string | Lý do nếu không sẵn sàng |
| `quota_available` | int | Số API keys còn available |
| `quota_total` | int | Tổng số API keys |
| `retry_after` | int | Giây nên đợi trước khi retry (nếu unavailable) |

**Example Usage (Caller Service):**

```javascript
async function shouldUploadToAIHub() {
  const resp = await fetch('https://stt.minhbv.com/v1/ai-hub/readiness');
  const data = await resp.json();
  
  if (!data.ready) {
    console.warn(`AI Hub unavailable: ${data.reason}`);
    scheduleRetry(data.retry_after * 1000);
    return false;
  }
  
  if (data.status === 'degraded') {
    rateLimiter.slowDown();  // Giảm tốc độ
  }
  
  return true;
}
```

## Webhook Response Structure

Sau khi xử lý xong, AI Hub sẽ gửi kết quả đến `webhook_url` qua POST request.

### Response Format - Full Success (100%)

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "filename": "document.pdf",
  "total_chunks": 50,
  "successful_chunks": 50,
  "failed_chunks": 0,
  "failed_chunk_indices": [],
  "data": [
    {
      "content": "Đoạn văn bản đầu tiên...",
      "vector": [0.123, -0.456, 0.789, ...]  // 768 dimensions
    },
    {
      "content": "Đoạn văn bản thứ hai...",
      "vector": [0.234, -0.567, 0.890, ...]
    }
  ],
  "text_full": "Toàn bộ nội dung trích xuất được...",
  "summary": "Tóm tắt nội dung document",
  "classification": {
    "category": "education",
    "confidence": 0.95
  },
  "metadata": {
    "school_id": "abc123",
    "uploader": "admin"
  }
}
```

### Response Format - Partial Success

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "partial_success",
  "filename": "document.pdf",
  "total_chunks": 50,
  "successful_chunks": 45,
  "failed_chunks": 5,
  "failed_chunk_indices": [3, 12, 28, 41, 49],
  "data": [
    {
      "content": "Chunk 0...",
      "vector": [...]
    }
    // Chỉ chứa 45 chunks thành công
  ],
  "text_full": "Toàn bộ text...",
  "summary": null,
  "classification": null,
  "metadata": {}
}
```

**⚠️ Quan trọng:** 
- `data` chỉ chứa **successful chunks**, không bao gồm failed chunks
- Caller service cần xử lý `failed_chunk_indices` để quyết định retry

### Response Format - Full Failure

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error": "Quota exceeded for all API keys",
  "filename": "document.pdf"
}
```

---

## Domain Mapping Configuration

Để giải quyết vấn đề cross-server communication (internal services không thể gọi được qua firewall/NAT), AI Hub hỗ trợ **Dynamic Domain Mapping**.

### Cấu hình trong `.env`

```bash
# Format: internal_host=public_domain (comma-separated)
WEBHOOK_DOMAIN_MAPPING=postgres-api:5002=https://thuvien.one.edu.vn,192.168.20.50=https://thuvien.one.edu.vn,192.168.22.11=https://stt.minhbv.com
```

### Hoạt động

1. **Protocol Fix:** Tự động sửa malformed URLs (`http:/host` → `http://host`)
2. **Domain Replacement:** Map internal hosts/IPs sang public domains
   - `http://postgres-api:5002/api/webhook` → `https://thuvien.one.edu.vn/api/webhook`
   - `http://192.168.20.50/callback` → `https://thuvien.one.edu.vn/callback`

---

## Stateless Retry Pattern

AI Hub **KHÔNG lưu** file gốc hay chunks. Caller service phải tự quản lý retry logic.

### Workflow

```
1. Caller Service → Upload file + webhook URL → AI Hub
2. AI Hub → Process → Send webhook response
3. Caller Service:
   - Nếu status = "completed": Lưu vectors, xong
   - Nếu status = "partial_success": Lưu vectors + Schedule retry
   - Nếu status = "failed": Schedule retry
4. Retry Worker (sau 24h):
   - Re-upload file gốc → AI Hub (full reprocessing)
```

### Implementation Example (Caller Service)

```javascript
// Webhook handler (e.g., ThuVienSo/postgres-api)
app.post('/api/webhook/ai_hub_result', async (req, res) => {
  const result = req.body;
  
  if (result.status === 'completed') {
    // Lưu tất cả vectors vào database
    await saveVectorsToDatabase(result.task_id, result.data);
    
  } else if (result.status === 'partial_success') {
    // Lưu vectors thành công
    await saveVectorsToDatabase(result.task_id, result.data);
    
    // Schedule retry sau 24h
    await scheduleRetry({
      filename: result.filename,
      failed_count: result.failed_chunks,
      retry_at: Date.now() + 24 * 3600 * 1000
    });
    
  } else if (result.status === 'failed') {
    // Schedule retry không lưu gì
    await scheduleRetry({
      filename: result.filename,
      retry_at: Date.now() + 24 * 3600 * 1000
    });
  }
  
  res.json({ success: true });
});

// Retry worker
async function retryWorker() {
  const retryItems = await getRetryQueue();
  for (const item of retryItems) {
    if (item.retry_at <= Date.now()) {
      // Re-upload file gốc lên AI Hub
      const fileBuffer = await getFileFromStorage(item.filename);
      await uploadToAIHub(fileBuffer, webhookUrl);
    }
  }
}
```

---

## Error Handling

### Common Errors

| HTTP Code | Error | Description | Solution |
|-----------|-------|-------------|----------|
| 400 | Bad Request | Thiếu file hoặc webhook_url | Kiểm tra request params |
| 413 | Payload Too Large | File quá lớn (>100MB) | Nén hoặc chia nhỏ file |
| 429 | Quota Exceeded | API keys hết quota | Retry sau 24h |
| 500 | Internal Server Error | Lỗi xử lý nội bộ | Kiểm tra logs, liên hệ admin |

### Retry Strategy (AI Hub Internal)

- **Webhook retry:** 3 lần với exponential backoff (2s, 4s, 8s)
- **Network errors:** Tự động retry
- **HTTP 4xx/5xx:** Log error và dừng

---

## Rate Limiting

### Gemini Embedding API

- **Free Tier:** 15 RPM/key
- **Total Keys:** 6 keys = ~90 RPM
- **Fallback:** Local embeddings (sentence-transformers) khi quota hết

### Best Practices

1. **Batch upload:** Upload nhiều file cùng lúc để tận dụng parallelism
2. **Off-peak hours:** Upload vào giờ thấp điểm (đêm khuya)
3. **Monitor quota:** Theo dõi usage để tránh quota exhaustion

---

## Security

1. **Webhook URL Validation:** AI Hub không validate webhook URL, caller service tự chịu trách nhiệm
2. **File Cleanup:** File tạm được xóa ngay sau processing (stateless)
3. **No Persistence:** AI Hub không lưu file gốc, chunks, hay vectors

---

## Support

- **Logs:** `docker logs stt-nova2`
- **Health Check:** `GET /` (FastAPI health endpoint)
- **Swagger UI:** `http://localhost:8000/docs`
