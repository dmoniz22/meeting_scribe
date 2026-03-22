#!/bin/bash
#
# start_audio.sh - Start MeetScribe audio daemon with EasyEffects routing
#
# Audio flow:
#   [Meeting App] → meetscribe_sink → easyeffects_sink → [speakers]
#                                       ↓
#                               Easy Effects Source
#                                       ↓
#                              [MeetScribe capture]
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd ~/projects/meeting_transcriber/audio-daemon

echo -e "${GREEN}=== MeetScribe Audio Setup ===${NC}"

# 1. Ensure EasyEffects is running
echo -e "\n${YELLOW}Step 1: Checking EasyEffects...${NC}"
if ! pgrep -x "easyeffects" > /dev/null; then
    echo "Starting EasyEffects..."
    easyeffects --gapplication-service &
    sleep 3
fi
echo -e "${GREEN}✓ EasyEffects running${NC}"

# 2. Create meetscribe_sink if it doesn't exist
echo -e "\n${YELLOW}Step 2: Creating meetscribe_sink...${NC}"
if ! pw-cli list-objects 2>/dev/null | grep -q "meetscribe_sink"; then
    pw-cli create-node adapter null-sink \
        node.name=meetscribe_sink \
        node.description="MeetScribe Recording Sink" \
        media.class=Audio/Sink \
        audio.channels=2 \
        audio.position=FL,FR 2>/dev/null || {
        echo -e "${YELLOW}pw-cli failed, trying pactl...${NC}"
        pactl load-module module-null-sink sink_name=meetscribe_sink 2>/dev/null || true
    }
    sleep 1
    echo -e "${GREEN}✓ meetscribe_sink created${NC}"
else
    echo -e "${GREEN}✓ meetscribe_sink already exists${NC}"
fi

# 3. Create audio routing
echo -e "\n${YELLOW}Step 3: Routing audio...${NC}"

# Clean old links
pw-link -d meetscribe_sink:playback_FL 2>/dev/null || true
pw-link -d meetscribe_sink:playback_FR 2>/dev/null || true

# Create new links: meetscribe_sink → easyeffects_sink
pw-link meetscribe_sink:playback_FL easyeffects_sink:input_FL 2>/dev/null && echo "  ✓ FL linked" || echo "  ⚠ FL already linked"
pw-link meetscribe_sink:playback_FR easyeffects_sink:input_FR 2>/dev/null && echo "  ✓ FR linked" || echo "  ⚠ FR already linked"

# Set default sink
pactl set-default-sink meetscribe_sink 2>/dev/null || true
echo -e "${GREEN}✓ Default sink set to meetscribe_sink${NC}"

# 4. Start audio daemon
echo -e "\n${YELLOW}Step 4: Starting audio daemon...${NC}"
source venv/bin/activate
python server_tcp.py --mic-device "easyeffects_source"

echo -e "\n${GREEN}=== MeetScribe Ready ===${NC}"

