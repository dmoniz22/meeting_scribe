#!/bin/bash
#
# setup_pipewire_easyeffects.sh - Setup MeetScribe with EasyEffects routing
# Routes: System Audio → meetscribe_sink → easyeffects_sink → speakers
# Capture: easyeffects_source (monitor)
#
# Usage:
#   ./setup_pipewire_easyeffects.sh      # Full setup
#   ./setup_pipewire_easyeffects.sh -r   # Restore routing only (skip sink creation)
#
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

RESTORE_ONLY=false
if [ "$1" = "-r" ] || [ "$1" = "--restore" ]; then
    RESTORE_ONLY=true
fi

echo -e "${GREEN}MeetScribe + EasyEffects Setup${NC}"
echo "================================"

# Check PipeWire
if ! pgrep -x "pipewire" > /dev/null; then
    echo -e "${RED}Error: PipeWire is not running${NC}"
    echo "Start it with: systemctl --user enable --now pipewire pipewire-pulse wireplumber"
    exit 1
fi
echo -e "${GREEN}✓ PipeWire is running${NC}"

# Step 1: Ensure EasyEffects is running
echo -e "\n${YELLOW}Step 1: Checking EasyEffects${NC}"
if ! pgrep -x "easyeffects" > /dev/null; then
    echo "Starting EasyEffects (gapplication service)..."
    easyeffects --gapplication-service &
    sleep 3
fi
echo -e "${GREEN}✓ EasyEffects is running${NC}"

# Step 2: Create virtual sink (only if not restore-only)
if [ "$RESTORE_ONLY" = false ]; then
    echo -e "\n${YELLOW}Step 2: Creating MeetScribe virtual sink${NC}"
    
    # Clean up existing
    pw-cli destroy-node meetscribe_sink 2>/dev/null || true
    sleep 0.5
    
    # Create meetscribe_sink
    SINK_RESULT=$(pw-cli create-node adapter null-sink \
        node.name=meetscribe_sink \
        node.description="MeetScribe Recording Sink" \
        media.class=Audio/Sink \
        audio.channels=2 \
        audio.position=FL,FR 2>&1)
    
    if echo "$SINK_RESULT" | grep -q "object.id"; then
        echo -e "${GREEN}✓ Created meetscribe_sink${NC}"
    else
        echo -e "${YELLOW}pw-cli method failed, trying pactl...${NC}"
        pactl load-module module-null-sink sink_name=meetscribe_sink module_name=meetscribe 2>/dev/null || true
    fi
    sleep 1
else
    echo -e "\n${YELLOW}Step 2: Skipping sink creation (restore mode)${NC}"
fi

# Step 3: Create audio routing using pactl (more reliable than pw-link)
echo -e "\n${YELLOW}Step 3: Routing audio streams${NC}"

# Clean up old loopbacks
for mod in $(pactl list modules short 2>/dev/null | grep "loopback" | awk '{print $1}'); do
    pactl unload-module "$mod" 2>/dev/null || true
done

# Create loopback: meetscribe_sink → easyeffects_sink
echo "  Creating loopback routing..."
LOOPBACK_ID=$(pactl load-module module-loopback \
    source=meetscribe_sink.monitor \
    sink=easyeffects_sink \
    latency_msec=20 2>/dev/null)

if [ -n "$LOOPBACK_ID" ]; then
    echo -e "  ${GREEN}✓ Loopback created (module $LOOPBACK_ID)${NC}"
else
    echo -e "  ${YELLOW}⚠ Loopback may already exist${NC}"
fi

# Verify routing
echo -e "\n  ${CYAN}Routing verification:${NC}"
pw-link -l 2>/dev/null | grep -E "(meetscribe|easyeffects)" | head -10 || echo "    (links created via pactl)"

# Set defaults
echo -e "\n${YELLOW}Step 4: Setting defaults${NC}"
pactl set-default-sink "$MS_SINK" 2>/dev/null && echo "  ✓ Default sink: $MS_SINK" || true

MIC_SOURCE=$(pactl info 2>/dev/null | grep "Default Source:" | cut -d: -f2 | xargs || echo "default")
echo "  ✓ Microphone: $MIC_SOURCE"

echo -e "\n${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Setup complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}Audio Flow:${NC}"
echo "  [Meeting App] → meetscribe_sink → easyeffects_sink → [speakers]"
echo "                                       ↓"
echo "                               Easy Effects Source"
echo "                                       ↓"
echo "                              [MeetScribe capture]"
echo ""
echo -e "${CYAN}Capture Device:${NC} Easy Effects Source (device index: 20)"
echo ""
echo -e "${YELLOW}To restore routing after restart:${NC}"
echo "  ~/projects/meeting_transcriber/audio-daemon/setup_pipewire_easyeffects.sh -r"
echo ""
echo -e "${YELLOW}To start recording:${NC}"
echo "  cd ~/projects/meeting_transcriber/audio-daemon"
echo "  ./start_audio.sh"
