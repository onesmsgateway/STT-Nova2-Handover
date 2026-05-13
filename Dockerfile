# Base on Python 3.11 to allow newer numpy versions (TTS constraint)
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Force IPv4 for apt to prevent hanging on IPv6
RUN echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4

# Install system dependencies
# ffmpeg: required for audio processing
# git: required for pip installing from git
# build-essential: required for compiling some python packages
# libsndfile1: required for soundfile/torchaudio
# rustc, cargo: required for compiling sudachipy and other tokenizers
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    build-essential \
    libsndfile1 \
    rustc \
    cargo \
    libssl-dev \
    libffi-dev \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage cache
COPY requirements.txt .

# Upgrade pip and install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run setup script to pull external dependencies (optional during build if network is stable)
# or just ensure directories exist for runtime setup
RUN chmod +x setup_models.sh && ./setup_models.sh

# Create directories for resources and temp files
RUN mkdir -p resource queue_data static/cache

# Expose port
EXPOSE 8123

# Default command
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8123"]
