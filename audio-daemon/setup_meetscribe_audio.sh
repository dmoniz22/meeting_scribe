#!/bin/bash
#
# setup_meetscribe_audio.sh - Simplified PipeWire + EasyEffects setup for MeetScribe
# Creates the audio routing needed to capture both system audio and microphone
#
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}MeetScribe Audio Setup (PipeWire + EasyEffects)${NC}"
echo "===================================================="

if ! pgrep -x "pipewire" > /dev/null; then
    echo -e "${RED}Error: PipeWire is not running${NC}"
    echo "Start with: pipewire &"
    exit 1
fi
echo -e "${GREEN}✓ PipeWire is running${NC}"

echo -e "\n${YELLOW}Step 1: Ensure meetscribe_sink exists${NC}"
if wpctl status 2>/dev/null | grep -q "meetscribe_sink"; then
    echo -e "${GREEN}✓ meetscribe_sink already exists${NC}"
else
    echo "Creating meetscribe_sink..."
    pactl load-module module-null-sink sink_name=meetscribe_sink module_name=meetscribe 2>/dev/null || true
    sleep 1
fi

SINK_ID=$(wpctl status 2>/dev/null | grep "meetscribe_sink" | grep -oP '^\s*\d+' | head -1)
echo "  Sink ID: $SINK_ID"

echo -e "\n${YELLOW}Step 2: Set meetscribe_sink as default output${NC}"
wpctl set-default-sink $SINK_ID 2>/dev/null || pactl set-default-sink meetscribe_sink
echo -e "${GREEN}✓ Default sink set to meetscribe_sink${NC}"

echo -e "\n${YELLOW}Step 3: Start EasyEffects if not running${NC}"
if pgrep -x "easyeffects" > /dev/null; then
    echo -e "${GREEN}✓ EasyEffects is already running${NC}"
else
    echo "Starting EasyEffects..."
    easyeffects --gapplication-service &
    sleep 2
    
    if pgrep -x "easyeffects" > /dev/null; then
        echo -e "${GREEN}✓ EasyEffects started${NC}"
    else
        echo -e "${YELLOW}⚠ EasyEffects may need GUI to start fully${NC}"
    fi
fi

echo -e "\n${YELLOW}Step 4: Wait for EasyEffects to create virtual devices${NC}"
sleep 3

echo -e "\n${YELLOW}Step 5: Check available sources for recording${NC}"
echo ""
wpctl status 2>/dev/null | grep -A10 "Sources:" || echo "  No sources found"

echo -e "\n${GREEN}Setup complete!${NC}"
echo ""
echo "Current audio routing:"
echo "  - System audio → meetscribe_sink → (EasyEffects) → recording capture"
echo "  - Microphone → (EasyEffects) → recording capture"
echo ""
echo "To test recording, run:"
echo "  python3 /home/dmoniz/projects/meeting_transcriber/audio-daemon/capture.py --duration 10"
echo ""
echo "If EasyEffects doesn't show in sources, start it with:"
echo "  easyeffects"