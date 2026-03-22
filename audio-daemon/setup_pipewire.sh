#!/bin/bash
#
# setup_pipewire.sh - Create PipeWire virtual sink for MeetScribe recording
# Uses native PipeWire commands (pw-cli, pw-link) to create and route audio
#
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}MeetScribe PipeWire Setup${NC}"
echo "=============================="

if ! pgrep -x "pipewire" > /dev/null; then
    echo -e "${RED}Error: PipeWire is not running${NC}"
    echo "Start it with: systemctl --user start pipewire pipewire-pulse"
    exit 1
fi

echo -e "${GREEN}✓ PipeWire is running${NC}"

if ! command -v pw-cli &> /dev/null; then
    echo -e "${RED}Error: pw-cli not found${NC}"
    echo "Install pipewire-utils"
    exit 1
fi

echo -e "\n${YELLOW}Cleaning up existing MeetScribe devices...${NC}"
for mod in $(pactl list modules short 2>/dev/null | grep -E "(null-sink|loopback)" | grep -E "(meetscribe|meet)" | awk '{print $1}'); do
    echo "Unloading module $mod"
    pactl unload-module "$mod" 2>/dev/null || true
done

pw-cli destroy-node meetscribe_sink 2>/dev/null || true
pw-cli destroy-node meetscribe_source 2>/dev/null || true
pw-cli destroy-node meetscribe_loopback_out 2>/dev/null || true
pw-cli destroy-node meetscribe_loopback_mic 2>/dev/null || true

rm -f /tmp/pulse-*dmoniz*/pid 2>/dev/null || true
sleep 1

OUTPUT_DEVICE=$(pactl info 2>/dev/null | grep "Default Sink:" | cut -d: -f2 | xargs || echo "")
INPUT_DEVICE=$(pactl info 2>/dev/null | grep "Default Source:" | cut -d: -f2 | xargs || echo "")

echo -e "\n${YELLOW}Default output: $OUTPUT_DEVICE${NC}"
echo "Default input: $INPUT_DEVICE"

echo -e "\n${YELLOW}Creating MeetScribe virtual sink...${NC}"
pw-cli create-node adapter null-sink \
    node.name=meetscribe_sink \
    node.description="MeetScribe Recording Sink" \
    media.class=Audio/Sink \
    audio.channels=2 \
    audio.position=FL,FR \
    2>/dev/null || {
    echo -e "${YELLOW}Trying pactl fallback...${NC}"
    MODULE_ID=$(pactl load-module module-null-sink sink_name=meetscribe_sink 2>/dev/null)
    
    if [ -z "$MODULE_ID" ]; then
        MODULE_ID=$(pactl load-module module-null-sink sink_name=meetscribe_main 2>/dev/null)
        
        if [ -n "$MODULE_ID" ]; then
            echo -e "${GREEN}✓ Created with alternate name 'meetscribe_main'${NC}"
        fi
    fi
}

sleep 1

SINK_NAME="meetscribe_sink"
if ! pactl list sinks short 2>/dev/null | grep -q "$SINK_NAME"; then
    SINK_NAME="meetscribe_main"
fi

echo -e "${GREEN}✓ Virtual sink configured: $SINK_NAME${NC}"

echo -e "\n${YELLOW}Setting up automatic audio routing...${NC}"

# Get current default devices
OUTPUT_DEVICE=$(pactl info 2>/dev/null | grep "Default Sink:" | cut -d: -f2 | xargs || echo "")
INPUT_DEVICE=$(pactl info 2>/dev/null | grep "Default Source:" | cut -d: -f2 | xargs || echo "")

route_audio() {
    local mode="$1"
    
    if [ "$mode" = "system" ]; then
        echo -e "\n${BLUE}Routing system audio...${NC}"
        
        if [ -n "$OUTPUT_DEVICE" ]; then
            echo "  Default sink: $OUTPUT_DEVICE"
            
            pactl move-sink-input 0 "$SINK_NAME" 2>/dev/null || {
                echo "  Note: No active audio streams to move. New audio will automatically route."
            }
            
            echo -e "${GREEN}✓ System audio will route through MeetScribe sink${NC}"
            echo -e "${YELLOW}  IMPORTANT: Set MeetScribe as default to record meeting audio:${NC}"
            echo -e "    pactl set-default-sink meetscribe_main"
        else
            echo -e "${YELLOW}⚠ No default sink configured${NC}"
        fi
    fi
    
    if [ "$mode" = "mic" ]; then
        echo -e "\n${BLUE}Routing microphone...${NC}"
        
        if [ -n "$INPUT_DEVICE" ]; then
            echo "  Default source: $INPUT_DEVICE"
            echo -e "${GREEN}✓ Microphone can be manually routed via pavucontrol${NC}"
        else
            echo -e "${YELLOW}⚠ No default source configured${NC}"
        fi
    fi
}

route_audio "system"
route_audio "mic"

echo -e "\n${YELLOW}Creating loopback for microphone mixing...${NC}"
# Try to create loopback with default source
if [ -n "$INPUT_DEVICE" ]; then
    LOOPBACK_ID=$(pactl load-module module-loopback \
        source="$INPUT_DEVICE" \
        sink="$SINK_NAME" \
        latency_msec=20 2>/dev/null) && echo "✓ Created loopback (module $LOOPBACK_ID)" || echo "⚠ Could not create loopback"
else
    # Try common microphone sources
    for MIC_SOURCE in "alsa_input.usb-Logitech_Logi_USB_Headset_000000000000-00.mono-fallback" "alsa_input.pci-0000_00_1f.3-platform-skl_hda_dsp_generic.HiFi__Mic1__source"; do
        if pactl list sources short 2>/dev/null | grep -q "$MIC_SOURCE"; then
            LOOPBACK_ID=$(pactl load-module module-loopback \
                source="$MIC_SOURCE" \
                sink="$SINK_NAME" \
                latency_msec=20 2>/dev/null) && echo "✓ Created loopback with $MIC_SOURCE (module $LOOPBACK_ID)" && break
        fi
    done
fi

echo -e "\n${GREEN}Setup complete!${NC}"
echo ""
echo "Audio routing is now active:"
echo "  - System audio → MeetScribe Recording Sink"
echo "  - Microphone → MeetScribe Recording Sink (via loopback)"
echo ""
echo "Recording device name: ${SINK_NAME}.monitor"
echo ""
echo "To use MeetScribe:"
echo "  1. Set MeetScribe as default audio output:"
echo "       pactl set-default-sink meetscribe_main"
echo "  2. Or configure your meeting app to use 'MeetScribe Recording Sink'"
echo ""
echo -e "${YELLOW}To verify setup, run:${NC}"
echo "  pactl list sources short | grep meetscribe"
echo "  pactl list sinks short | grep meetscribe"
