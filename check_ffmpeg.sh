#!/bin/bash
# Script để kiểm tra ffmpeg trong container

echo "🔍 Checking ffmpeg availability in container..."

# Check if ffmpeg is installed
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg is installed"
    ffmpeg -version | head -1
else
    echo "❌ FFmpeg is NOT installed"
fi

# Check if curl is installed
if command -v curl &> /dev/null; then
    echo "✅ Curl is installed"
    curl --version | head -1
else
    echo "❌ Curl is NOT installed"
fi

# Check system packages
echo ""
echo "📦 Checking installed packages..."
dpkg -l | grep -E "(ffmpeg|curl)" || echo "No ffmpeg/curl packages found"

# Check PATH
echo ""
echo "🛤️  PATH: $PATH"

# Check /usr/bin for ffmpeg
echo ""
echo "🔍 Checking /usr/bin for ffmpeg..."
ls -la /usr/bin/ffmpeg* 2>/dev/null || echo "No ffmpeg in /usr/bin"

# Check /usr/local/bin for ffmpeg
echo ""
echo "🔍 Checking /usr/local/bin for ffmpeg..."
ls -la /usr/local/bin/ffmpeg* 2>/dev/null || echo "No ffmpeg in /usr/local/bin"

echo ""
echo "🎯 Summary:"
echo "  - If ffmpeg is missing, the fallback to curl should work"
echo "  - Check container build logs for any errors"
echo "  - Consider rebuilding container with: docker-compose build --no-cache"
