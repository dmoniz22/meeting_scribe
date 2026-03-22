#!/bin/bash
set -e

cd /home/dmoniz/projects/meeting_transcriber

# Kill existing uvicorn
pkill -f "uvicorn.*8003" 2>/dev/null || true
sleep 1

# Activate venv
source venv/bin/activate

# Export environment
cd backend
export DATABASE_URL="postgresql+asyncpg://meetscribe:Birdsey5%40@localhost:5434/meetscribe"
export REDIS_URL="redis://localhost:6380/0"
export SECRET_KEY="dev-secret-key-change-this"
export RECORDINGS_PATH="./recordings"
export OLLAMA_BASE_URL="http://localhost:11434"

# Start API
exec uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
