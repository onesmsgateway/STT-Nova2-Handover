#!/bin/bash
# ==============================================================================
# STT-Nova2 Production Deployment Script (1-Step Solution)
# ==============================================================================

set -e # Exit on error

echo "🚀 Starting Production Deployment for STT-Nova2..."

# 1. Pull latest code (Force update from main)
echo "📥 Updating source code from Git..."
git pull origin main

# 2. Setup external dependencies (Models & Libs)
echo "📦 Configuring AI models and libraries..."
chmod +x scripts/init_models.sh
./scripts/init_models.sh

# 2.5 Check Environment Config
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    if [ -f .env.example ]; then
        echo "📄 Creating .env from .env.example..."
        cp .env.example .env
        echo "❗ PLEASE EDIT .env file with your API keys and DB credentials before running again."
        # Optional: exit 1 to force user edit, or continue with defaults
        # exit 1 
    else
        echo "❌ .env.example not found. Please create .env manually."
        exit 1
    fi
fi

# 3. Detect Docker Compose version
if command -v docker-compose &> /dev/null; then
  DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
  DOCKER_COMPOSE="docker compose"
else
  echo "❌ Error: Neither 'docker-compose' nor 'docker compose' found. Please install Docker."
  exit 1
fi

echo "🐳 Using: $DOCKER_COMPOSE"

# 4. Clean up Docker environment
echo "🗑️  Stopping old services and cleaning up..."
$DOCKER_COMPOSE down --remove-orphans || true
docker rm -f stt-nova2 || true

# Aggressive cleanup to free up disk space
echo "🧹 Pruning unused Docker images and build cache..."
docker system prune -af --volumes || true
docker builder prune -af || true

# 5. Build and Start Services
echo "🏗️  Building and Starting Production Services (App + Vector DB)..."
# Force rebuild with --no-cache to ensure all code changes are picked up
$DOCKER_COMPOSE build --no-cache
$DOCKER_COMPOSE up -d

# 6. Verification
echo "📊 Checking container status..."
sleep 5
$DOCKER_COMPOSE ps

echo ""
echo "✅ Deployment Successful!"
echo "🌐 API Documentation: http://localhost:8000/docs"
echo "🖥️  Live Dashboard: http://localhost:8000/"
echo "📜 Tailing logs... (Press Ctrl+C to stop viewing logs)"
$DOCKER_COMPOSE logs -f stt-nova2
