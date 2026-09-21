#!/usr/bin/env bash
# UniServe — Development Environment Setup Script
# Run this script to set up the full development environment.

set -euo pipefail

echo "🔧 UniServe — Setting up development environment..."

# ---- Check prerequisites ----
echo "📋 Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed."; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ Node.js is required but not installed."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ Docker is required but not installed."; exit 1; }

echo "✅ Prerequisites found."

# ---- Start infrastructure ----
echo ""
echo "🐳 Starting Docker services..."
docker compose up -d postgres redis
echo "✅ Docker services started."

# ---- Wait for PostgreSQL ----
echo ""
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 3
docker compose exec postgres pg_isready -U uniserve -d uniserve_dev || {
    echo "❌ PostgreSQL is not ready. Check Docker logs."
    exit 1
}
echo "✅ PostgreSQL is ready."

# ---- Set up backend ----
echo ""
echo "🐍 Setting up backend API..."
cd apps/api

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# Activate virtual environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

pip install -e ".[dev]" -q

# Copy .env if it doesn't exist
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "📝 Created .env from .env.example"
fi

echo "✅ Backend API setup complete."

cd ../..

# ---- Set up web app ----
echo ""
echo "🌐 Setting up web application..."
cd apps/web
npm install --silent
cd ../..

# ---- Set up mobile app ----
echo ""
echo "📱 Setting up mobile application..."
cd apps/mobile
npm install --silent
cd ../..

# ---- Done ----
echo ""
echo "🎉 UniServe development environment is ready!"
echo ""
echo "Next steps:"
echo "  1. Start the API:    cd apps/api && uvicorn app.main:app --reload"
echo "  2. Start the web:    cd apps/web && npm run dev"
echo "  3. Start mobile:     cd apps/mobile && npx expo start"
echo "  4. API docs:         http://localhost:8000/api/docs"
echo "  5. Health check:     curl http://localhost:8000/api/v1/health"
