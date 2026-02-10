#!/bin/bash
#
# setup_pipewire.sh - Create PipeWire virtual sink for MeetScribe recording
# This script creates a virtual recording sink and routes system audio + mic into it
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}MeetScribe PipeWire Setup${NC}"
echo "============================"

# Check if PipeWire is running
if ! pgrep -x "pipewire" > /dev/null; then
    echo -e "${RED}Error: PipeWire is not running${NC}"
    echo "Please start PipeWire first:"
    echo "  systemctl --user start pipewire"
    exit 1
fi

echo -e "${GREEN}✓ PipeWire is running${NC}"

# Clean up any existing MeetScribe loopback modules
echo -e "\n${YELLOW}Cleaning up existing MeetScribe modules...${NC}"
pactl list modules short | grep -E "(meetscribe|loopback)" | awk '{print $1}' | while read -r module_id; do
    echo "Removing module $module_id"
    pactl unload-module "$module_id" 2>/dev/null || true
done

# Get default output device (speakers/headphones)
OUTPUT_DEVICE=$(pactl info | grep "Default Sink:" | cut -d: -f2 | xargs)
echo -e "\n${YELLOW}Default output device: $OUTPUT_DEVICE${NC}"

# Get default input device (microphone)
INPUT_DEVICE=$(pactl info | grep "Default Source:" | cut -d: -f2 | xargs)
echo "Default input device: $INPUT_DEVICE"

# Create the virtual recording sink
echo -e "\n${YELLOW}Creating MeetScribe virtual recording sink...${NC}"
pactl load-module module-null-sink \
    sink_name=meetscribe_sink \
    sink_properties="device.description='MeetScribe Recording Sink'" \
    rate=16000 \
    channels=2 \
    channel_map=front-left,front-right

echo -e "${GREEN}✓ Virtual sink created${NC}"

# Create virtual source from the sink monitor
echo -e "\n${YELLOW}Creating virtual source for capture...${NC}"
pactl load-module module-virtual-source \
    source_name=meetscribe_source \
    master=meetscribe_sink.monitor \
    source_properties="device.description='MeetScribe Recording Source'"

echo -e "${GREEN}✓ Virtual source created${NC}"

# Route system output monitor to virtual sink (left channel)
echo -e "\n${YELLOW}Routing system audio to virtual sink...${NC}"
pactl load-module module-loopback \
    source="${OUTPUT_DEVICE}.monitor" \
    sink=meetscribe_sink \
    rate=16000 \
    channels=2 \
    channel_map=front-left,front-left \
    sink_dont_move=true \
    source_dont_move=true

echo -e "${GREEN}✓ System audio routed (left channel)${NC}"

# Route microphone to virtual sink (right channel)
echo -e "\n${YELLOW}Routing microphone to virtual sink...${NC}"
pactl load-module module-loopback \
    source="$INPUT_DEVICE" \
    sink=meetscribe_sink \
    rate=16000 \
    channels=2 \
    channel_map=front-right,front-right \
    sink_dont_move=true \
    source_dont_move=true

echo -e "${GREEN}✓ Microphone routed (right channel)${NC}"

# Verify setup
echo -e "\n${GREEN}Setup complete!${NC}"
echo -e "\n${YELLOW}Active MeetScribe devices:${NC}"
pactl list sinks short | grep -E "(meetscribe|Name)"
echo ""
pactl list sources short | grep -E "(meetscribe|Name)"

echo -e "\n${GREEN}Audio routing:${NC}"
echo "  System Output (L) → MeetScribe Sink → MeetScribe Source → App"
echo "  Microphone    (R) → MeetScribe Sink → MeetScribe Source → App"

echo -e "\n${YELLOW}To remove these devices, run:${NC}"
echo "  pactl list modules short | grep loopback | awk '{print \$1}' | xargs -I {} pactl unload-module {}"
echo "  pactl unload-module $(pactl list modules short | grep null-sink | grep meetscribe | awk '{print $1}')"
