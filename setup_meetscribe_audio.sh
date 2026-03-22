#!/bin/bash
#
# setup_meetscribe_audio.sh - Complete PipeWire + EasyEffects setup for MeetScribe
# This creates proper audio routing for capturing both system audio and microphone
#
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     MeetScribe Audio Setup (PipeWire + EasyEffects)     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check PipeWire
if ! pgrep -x "pipewire" > /dev/null; then
    echo -e "${RED}✗ Error: PipeWire is not running${NC}"
    echo "Start with: pipewire &"
    exit 1
fi
echo -e "${GREEN}✓ PipeWire is running${NC}"

# Clean up old MeetScribe modules
echo -e "\n${YELLOW}Cleaning up old configuration...${NC}"
for mod_id in $(pactl list modules short 2>/dev/null | grep -E "loopback" | grep -E "meetscribe|easyeffects" | awk '{print $1}'); do
    pactl unload-module "$mod_id" 2>/dev/null && echo "  Removed module $mod_id"
done

# Step 1: Ensure meetscribe_sink exists
echo -e "\n${YELLOW}Step 1: Creating MeetScribe virtual sink${NC}"
if wpctl status 2>/dev/null | grep -q "meetscribe_sink"; then
    echo -e "${GREEN}✓ meetscribe_sink already exists${NC}"
else
    pactl load-module module-null-sink sink_name=meetscribe_sink module_name=meetscribe
    sleep 1
    echo -e "${GREEN}✓ Created meetscribe_sink${NC}"
fi

# Set default sink to meetscribe_sink
wpctl set-default-sink meetscribe_sink 2>/dev/null || pactl set-default-sink meetscribe_sink
echo "  Default sink set to meetscribe_sink"

# Step 2: Start EasyEffects if needed
echo -e "\n${YELLOW}Step 2: Starting EasyEffects${NC}"
if pgrep -x "easyeffects" > /dev/null; then
    echo -e "${GREEN}✓ EasyEffects is already running${NC}"
else
    easyeffects --gapplication-service &
    sleep 3
    if pgrep -x "easyeffects" > /dev/null; then
        echo -e "${GREEN}✓ EasyEffects started${NC}"
    else
        echo -e "${YELLOW}⚠ Started in background - may need GUI to fully initialize${NC}"
    fi
fi

# Wait for EasyEffects devices to appear
echo -e "\n${YELLOW}Waiting for EasyEffects virtual devices...${NC}"
for i in 1 2 3 4 5; do
    if wpctl status 2>/dev/null | grep -q "Easy Effects Sink"; then
        break
    fi
    sleep 1
done

# Step 3: Set up loopback routing
echo -e "\n${YELLOW}Step 3: Setting up audio routing${NC}"

# Detect microphone
MIC_SOURCE=$(pactl list sources short 2>/dev/null | grep -i "logitech" | grep -i "mono" | grep -v "monitor" | awk '{print $2}' | head -1)
if [ -z "$MIC_SOURCE" ]; then
    MIC_SOURCE=$(pactl list sources short 2>/dev/null | grep -i "headset" | grep -v "monitor" | awk '{print $2}' | head -1)
fi

if [ -z "$MIC_SOURCE" ]; then
    echo -e "${YELLOW}⚠ Could not detect microphone, using default${NC}"
    MIC_SOURCE="default"
fi
echo "  Detected microphone: $MIC_SOURCE"

# System audio -> EasyEffects (loopback from meetscribe_sink monitor)
echo "  Creating system audio loopback..."
pactl load-module module-loopback source=meetscribe_sink.monitor sink=easyeffects_sink latency_msec=20 2>/dev/null
echo "    System audio routed through EasyEffects"

# Microphone -> EasyEffects
echo "  Creating microphone loopback..."
pactl load-module module-loopback source="$MIC_SOURCE" sink=easyeffects_sink latency_msec=20 2>/dev/null
echo "    Microphone routed through EasyEffects"

# Step 4: Summary
echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                     Setup Complete!                       ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Audio Routing:"
echo "  ┌─────────────────┐      ┌──────────────────┐      ┌─────────────┐"
echo "  │ System Audio    │─────▶│ meetscribe_sink   │─────▶│ EasyEffects │"
echo "  └─────────────────┘      └──────────────────┘      │     Sink    │"
echo "  ┌─────────────────┐                           ┌───▶│             │"
echo "  │ Microphone      │───────────────────────────▶│    └──────┬──────┘"
echo "  └─────────────────┘                           │           │"
echo "                                                   │    ┌──────▼──────┐"
echo "                                                   │    │EasyEffects  │"
echo "                                                   │    │  Source     │────▶ Capture
echo "                                                   │    └────────────┘"
echo ""
echo "To test recording:"
echo "  python3 audio-daemon/capture.py --duration 10 --output /tmp/test"
echo ""
echo "To start the audio daemon:"
echo "  ./start-audio-daemon.sh"
echo ""
echo "Check routing anytime with: wpctl status"