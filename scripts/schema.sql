-- PostgreSQL Init Script for STT-Nova2 Project

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Bảng quản lý tenant (được dùng để tra cứu schema của từng school/tenant)
CREATE TABLE IF NOT EXISTS public.tenants (
    id SERIAL PRIMARY KEY,
    school_code VARCHAR(50) UNIQUE NOT NULL,
    schema_name VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng lưu trữ log các nội dung vi phạm moderation (flagged_content)
CREATE TABLE IF NOT EXISTS public.flagged_content (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(255),
    ip_address VARCHAR(255),
    user_identifier VARCHAR(255),
    content TEXT,
    flagged_category VARCHAR(255),
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bảng dữ liệu gọi (CDR - Call Detail Record) của hệ thống tổng đài
-- Lưu ý: STT-Nova2 sẽ cập nhật kết quả transcript và summary vào bảng này qua cdr_uuid
CREATE TABLE IF NOT EXISTS public.cdr (
    cdr_uuid UUID PRIMARY KEY,
    transcript TEXT,
    summary TEXT,
    call_topic VARCHAR(255) DEFAULT 'N/A'
    -- Các trường khác của bảng CDR được quản lý bởi hệ thống tổng đài
);

-- ==========================================
-- Mẫu Schema cho một Tenant (Ví dụ: schema `tenant_sample`)
-- ==========================================

CREATE SCHEMA IF NOT EXISTS tenant_sample;

CREATE TABLE IF NOT EXISTS tenant_sample.resources (
    id UUID PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tenant_sample.resource_vectors (
    id SERIAL PRIMARY KEY,
    resource_id UUID REFERENCES tenant_sample.resources(id) ON DELETE CASCADE,
    content_chunk TEXT,
    embedding VECTOR(768), -- Dimension tuỳ theo model (VD: Gemini/PhoWhisper)
    metadata JSONB
);
