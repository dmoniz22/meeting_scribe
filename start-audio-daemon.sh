#!/bin/bash
# MeetScribe Startup Script

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_DIR="$SCRIPT_DIR/audio-daemon"
VENV_PATH="$AUDIO_DIR/venv"
PIDFILE="/tmp/meetscribe-audio.pid"
PORT=8081

echo -e "${GREEN}MeetScribe Audio Daemon Startup${NC}"
echo "================================"

# Check if parec is installed
if ! command -v parec &> /dev/null; then
    echo -e "${RED}Error: parec not found. Install pulseaudio-utils${NC}"
    exit 1
fi

# Create virtual devices if needed
if ! pactl list sources | grep -q "meetscribe_source"; then
    echo "Creating virtual devices..."
    pactl load-module module-null-sink sink_name=meetscribe_sink 2>/dev/null || true
    pactl load-module module-virtual-source source_name=meetscribe_source master=meetscribe_sink.monitor 2>/dev/null || true
    OUTPUT_DEVICE=$(pactl info | grep "Default Sink:" | cut -d: -f2 | xargs)
    INPUT_DEVICE=$(pactl info | grep "Default Source:" | cut -d: -f2 | xargs)
    pactl load-module module-loopback source="${OUTPUT_DEVICE}.monitor" sink=meetscribe_sink 2>/dev/null || true
    pactl load-module module-loopback source="$INPUT_DEVICE" sink=meetscribe_sink 2>/dev/null || true
    echo -e "${GREEN}✓ Virtual devices created${NC}"
else
    echo -e "${GREEN}✓ Virtual devices already exist${NC}"
fi

# Check if already running
if [ -f "$PIDFILE" ] && kill -0 $(cat "$PIDFILE") 2>/dev/null; then
    echo -e "${YELLOW}Already running (PID: $(cat $PIDFILE))${NC}"
    exit 0
fi

# Check venv exists
if [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo -e "${RED}Error: Virtual environment not found at $VENV_PATH${NC}"
    exit 1
fi

source "$VENV_PATH/bin/activate"

echo -e "${YELLOW}Starting audio daemon on port $PORT...${NC}"
cd "$AUDIO_DIR"
python server_tcp.py --host 0.0.0.0 --port "$PORT" &
echo $! > "$PIDFILE"

sleep 2
if kill -0 $(cat "$PIDFILE") 2>/dev/null; then
    echo -e "${GREEN}✓ Audio daemon started${NC}"
    echo "  Dashboard: http://localhost:3000"
    echo "Press Ctrl+C to stop"
    wait $(cat "$PIDFILE")
else
    echo -e "${RED}✗ Failed to start${NC}"
    rm -f "$PIDFILE"
    exit 1
fi
