#!/bin/bash

# Configuration
MODEL_DIR="resource/models/vixtts"
MODEL_PATH="$MODEL_DIR/model.pth"
VIENEU_LIB="src/libs/VieNeu-TTS"

echo "🚀 Starting setup for large models and libraries..."

# 1. Setup Models
mkdir -p "$MODEL_DIR"

if [ ! -f "$MODEL_PATH" ]; then
    echo "📥 XTTS Model not found. Downloading (1.8GB) from Hugging Face..."
    # Official VixTTS model path - using capleaf/viXTTS repo
    MODEL_URL="https://huggingface.co/capleaf/viXTTS/resolve/main/model.pth?download=true"
    
    echo "Using curl to download from: $MODEL_URL"
    curl -L -o "$MODEL_PATH" "$MODEL_URL" || {
        echo "❌ Download failed with curl. Trying wget..."
        wget -O "$MODEL_PATH" "$MODEL_URL" || {
            echo "❌ All download methods failed. Please download manually from:"
            echo "   https://huggingface.co/capleaf/viXTTS/blob/main/model.pth"
            echo "   and place it in $MODEL_DIR"
        }
    }
else
    echo "✅ XTTS Model already exists."
fi

# 2. Setup VieNeu-TTS
if [ ! -d "$VIENEU_LIB" ]; then
    echo "📥 Cloning VieNeu-TTS library..."
    git clone https://github.com/pnnbao97/VieNeu-TTS.git "$VIENEU_LIB"
else
    echo "✅ VieNeu-TTS library already exists."
fi

echo "✨ Setup complete."
