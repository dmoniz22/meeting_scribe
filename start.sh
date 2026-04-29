#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Starting MeetScribe services..."

# Start Docker services
echo "Starting Docker containers..."
docker compose up -d

# Wait for containers to be healthy
echo "Waiting for API to be healthy..."
until curl -sf http://localhost:8005/api/v1/health > /dev/null 2>&1; do
    sleep 1
done

# Start audio daemon if not running
if ! pgrep -f "server_tcp.py" > /dev/null; then
    echo "Starting audio daemon..."
    cd audio-daemon
    nohup python3 server_tcp.py > /tmp/audio-daemon.log 2>&1 &
    cd ..
    sleep 2
fi

# Verify audio daemon
if curl -sf http://localhost:9000/health > /dev/null 2>&1; then
    echo "Audio daemon: OK"
else
    echo "Warning: Audio daemon not responding"
fi

echo ""
echo "MeetScribe is ready!"
echo "  Frontend: http://localhost:3001"
echo "  API:      http://localhost:8005"
