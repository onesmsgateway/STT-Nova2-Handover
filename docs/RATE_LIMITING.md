# API Rate Limiting Best Practices

## Overview
Khi sử dụng nhiều API keys với round robin, cần có chiến lược rate limiting phù hợp để tránh hit quota limits.

## Gemini Free Tier Limits (2025)

| Model | RPM | RPD | TPM |
|-------|-----|-----|-----|
| gemini-1.5-flash | 15 | 1,500 | 1,000,000 |
| gemini-2.5-flash | 10 | 500 | 250,000 |
| text-embedding-004 | 1,500 | 10,000 | - |

## Rate Limiting Strategies

### 1. Per-Key Rate Limiter
Track số requests cho từng key trong sliding window (1 phút):
```python
class PerKeyRateLimiter:
    def __init__(self, rpm_limit=15):
        self.rpm_limit = rpm_limit
        self.key_requests = {}  # {key: [timestamp1, timestamp2, ...]}
```

### 2. Global Throttle
Delay giữa các request để tránh burst:
```
Total RPM capacity = num_keys × rpm_per_key
Min delay = 60 / Total RPM
Example: 6 keys × 15 RPM = 90 RPM → delay = 0.67s
```

### 3. Key Cooldown
Khi 1 key hit 429, đánh dấu cooldown và skip sang key khác:
```python
key_cooldowns = {
    "key1": datetime(2025, 1, 23, 10, 30, 0),  # Cooldown until
    "key2": None  # Available
}
```

### 4. Adaptive Backoff
Khi hit rate limit, tăng delay exponentially:
```
Attempt 1: wait 5s
Attempt 2: wait 10s
Attempt 3: wait 20s
Max: 60s
```

## Fallback Strategies (New feature 2026-01-26)

Khi tất cả Google API Keys bị hết quota (429) hoặc lỗi, hệ thống sẽ tự động chuyển sang cơ chế dự phòng:

### 1. Chat & Summarization (Text Generation)
- **Fallback Provider:** Groq API
- **Model:** `llama-3.3-70b-versatile`
- **Rate Limit:** 30 RPM (Free Tier), 14,400 RPD
- **Behavior:**
  - Nếu tất cả 6 Gemini keys trả về 429/500/Timeout
  - Hệ thống chuyển ngay sang Groq để trả lời user
  - Hỗ trợ Round Robin cho nhiều Groq keys (`GROQ_API_KEYS=k1,k2`)

### 2. Embeddings (Vectorization)
- **Fallback Provider:** Local Model (`sentence-transformers`)
- **Model:** `all-mpnet-base-v2` (**768 dimensions**)
- **Behavior:**
  - Nếu Gemini `text-embedding-004` (768 dims) lỗi quota
  - Hệ thống tự load local model xuống RAM (~420MB) và embed trên CPU
  - **Lưu ý:** Tương thích hoàn toàn vector dimension với Gemini (768), không bị lỗi size mismatch trong DB.

## Implementation Checklist
- [x] Round robin key rotation
- [x] Smart 429 detection với retry delay từ API
- [x] Exponential backoff
- [x] Per-key request tracking (sliding window)
- [x] Global throttle (min delay between requests)
- [x] Key cooldown tracking
- [x] **LLM Fallback (Groq)** ✅ Implemented 2026-01-26
- [x] **Embedding Fallback (Local)** ✅ Implemented 2026-01-26

## Calculation Example

**Config:** 6 API keys, gemini-2.0-flash + Fallback
```
Gemini Total: 90 RPM, 9,000 RPD (Free)
Groq Fallback: 30 RPM, 14,400 RPD (Free)

Total Theoretical Capacity: 
- 120 RPM (Burst safe)
- 23,000+ requests/day

## Fast Fallback Logic
Khi Gemini trả về lỗi 429 (Quota Exceeded):
1. Hệ thống **NGẮT NGAY** vòng retry của Gemini.
2. Chuyển ngay lập tức sang Fallback (Groq hoặc Local Embedding).
3. **Không chờ đợi** retry backoff (tiết kiệm 5-30s cho user).
4. Vẫn áp dụng rate limits cho Groq để tránh spam.
```

