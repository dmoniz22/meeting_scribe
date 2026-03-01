#!/bin/bash
# MeetScribe Startup Script
# Starts Docker Compose and the Audio Daemon

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="meetscribe"

echo "=========================================="
echo "  MeetScribe - Meeting Transcriber"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

echo "Step 1: Starting Docker Compose services..."
cd "$SCRIPT_DIR"
docker compose up -d

echo ""
echo "Step 2: Waiting for services to be healthy..."
sleep 3

# Check if API is responding
for i in {1..10}; do
    if curl -s http://localhost:8003/health > /dev/null 2>&1 || curl -s http://localhost:8003/api/v1/health > /dev/null 2>&1; then
        echo "✓ API is ready"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "⚠ API may still be starting..."
    else
        echo "  Waiting for API... ($i/10)"
        sleep 2
    fi
done

echo ""
echo "Step 3: Checking Audio Daemon..."

# Function to check if audio daemon is running
check_audio_daemon() {
    curl -s http://localhost:8080/status > /dev/null 2>&1 || curl -s http://localhost:8080/ > /dev/null 2>&1
}

if check_audio_daemon; then
    echo "✓ Audio Daemon is already running"
else
    echo "Step 4: Starting Audio Daemon..."
    
    # Check if audio-daemon venv exists
    if [ ! -d "$SCRIPT_DIR/audio-daemon/venv" ]; then
        echo "  Setting up Audio Daemon environment..."
        cd "$SCRIPT_DIR/audio-daemon"
        python -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    fi
    
    # Start audio daemon in background
    cd "$SCRIPT_DIR/audio-daemon"
    source venv/bin/activate
    
    # Check if already running in screen/tmux
    if command -v screen &> /dev/null; then
        screen -dmS meetscribe-audio bash -c "source venv/bin/activate && python server.py"
        echo "✓ Audio Daemon started in screen session 'meetscribe-audio'"
        echo "  To view: screen -r meetscribe-audio"
        echo "  To detach: Ctrl+A then D"
    elif command -v tmux &> /dev/null; then
        tmux new-session -d -s meetscribe-audio "source venv/bin/activate && python server.py"
        echo "✓ Audio Daemon started in tmux session 'meetscribe-audio'"
        echo "  To view: tmux attach -t meetscribe-audio"
        echo "  To detach: Ctrl+B then D"
    else
        # Run in background with nohup
        nohup bash -c "source venv/bin/activate && python server.py" > "$SCRIPT_DIR/audio-daemon.log" 2>&1 &
        echo "✓ Audio Daemon started in background"
        echo "  Logs: $SCRIPT_DIR/audio-daemon.log"
    fi
    
    sleep 2
    
    if check_audio_daemon; then
        echo "✓ Audio Daemon is now running"
    else
        echo "⚠ Audio Daemon may still be starting..."
    fi
fi

echo ""
echo "=========================================="
echo "  MeetScribe is Ready!"
echo "=========================================="
echo ""
echo "Services:"
echo "  📊 Dashboard:    http://localhost:3000"
echo "  📚 API Docs:     http://localhost:8003/docs"
echo "  🔧 API:          http://localhost:8003"
echo ""
echo "Useful commands:"
echo "  Stop all:        cd $SCRIPT_DIR && docker compose down"
echo "  View logs:       docker compose logs -f"
echo "  Audio daemon:    screen -r meetscribe-audio  (or tmux attach -t meetscribe-audio)"
echo ""
echo "=========================================="
