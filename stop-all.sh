#!/bin/bash
# MeetScribe - Stop All Services

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "\n${YELLOW}Stopping MeetScribe services...${NC}"

# Stop audio daemon
if [ -f ".audio.pid" ]; then
    kill $(cat .audio.pid) 2>/dev/null || true
    rm .audio.pid
    echo -e "${GREEN}✓ Audio daemon stopped${NC}"
fi

# Also kill any running audio daemon
pkill -f "python.*server.py" 2>/dev/null || true

# Stop Docker containers
echo -e "${YELLOW}Stopping Docker containers...${NC}"
docker compose down
echo -e "${GREEN}✓ Docker containers stopped${NC}"

echo -e "\n${GREEN}All services stopped${NC}"
echo ""
echo "Note: PipeWire virtual devices remain active."
echo "To remove them manually: pactl unload-module \$(pactl list modules short | grep meetscribe | awk '{print \$1}')"
