#!/bin/bash
# MeetScribe Master Startup Script
# Starts all services including Docker containers and audio daemon

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "MeetScribe - Starting Services"
echo "=========================================="

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

check_port() {
    local port=$1
    if lsof -Pi :"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 1. Setup PipeWire Virtual Devices
echo -e "\n${YELLOW}Setting up PipeWire virtual audio devices...${NC}"
cd audio-daemon
if [ -x "./setup_pipewire.sh" ]; then
    ./setup_pipewire.sh
    echo -e "${GREEN}✓ PipeWire devices configured${NC}"
else
    chmod +x ./setup_pipewire.sh
    ./setup_pipewire.sh
    echo -e "${GREEN}✓ PipeWire devices configured${NC}"
fi
cd "$SCRIPT_DIR"

# 2. Build and start Docker services
echo -e "\n${YELLOW}Building and starting Docker services...${NC}"
docker compose build
docker compose up -d

# Wait for services to be healthy
echo -e "\n${YELLOW}Waiting for services to be ready...${NC}"
sleep 10

# 3. Start Audio Daemon (runs on host for PipeWire access)
echo -e "\n${YELLOW}Starting Audio Daemon...${NC}"
cd audio-daemon

if [ ! -d "venv" ]; then
    echo "Creating audio-daemon virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

if pgrep -f "python.*server.py" > /dev/null; then
    echo -e "${GREEN}✓ Audio daemon already running${NC}"
else
    pip install -q -r requirements.txt 2>/dev/null || true
    nohup python server_tcp.py > ../audio_daemon.log 2>&1 &
    echo $! > ../.audio.pid
    sleep 2
    echo -e "${GREEN}✓ Audio daemon started${NC}"
fi

cd "$SCRIPT_DIR"

echo -e "\n=========================================="
echo -e "${GREEN}MeetScribe is ready!${NC}"
echo "=========================================="
echo ""
echo "Services:"
echo "  - Web App:        http://localhost:3001"
echo "  - API:            http://localhost:8005"
echo "  - API Docs:       http://localhost:8005/docs"
echo "  - PostgreSQL:     localhost:5433"
echo "  - Redis:          localhost:6381"
echo ""
echo "Audio Daemon: Running on port 8080"
echo ""
echo "To stop: docker compose down"
echo "To view logs: docker compose logs -f"
