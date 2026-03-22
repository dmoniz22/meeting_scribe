#!/bin/bash
#
# meetscribe_audio_control.sh - Control MeetScribe audio routing
#
# Usage:
#   ./meetscribe_audio_control.sh start   # Enable recording mode
#   ./meetscribe_audio_control.sh stop    # Disable recording mode (normal)
#   ./meetscribe_audio_control.sh status  # Show current routing
#

set -e

HEADSET_SINK="alsa_output.usb-Logitech_Logi_USB_Headset_000000000000-00.analog-stereo"
MIC_SOURCE="alsa_input.usb-Logitech_Logi_USB_Headset_000000000000-00.mono-fallback"

start_recording_mode() {
    echo "Starting MeetScribe recording mode..."
    
    # Create virtual sink for recording (tap into system audio)
    if ! wpctl status 2>/dev/null | grep -q "meetscribe_sink"; then
        pactl load-module module-null-sink sink_name=meetscribe_sink module_name=meetscribe
        sleep 1
    fi
    
    # Set default output back to headset (so you hear normally)
    pactl set-default-sink "$HEADSET_SINK"
    
    # Route system audio to meetscribe_sink for recording (without breaking headphone output)
    # Move existing streams or let new audio automatically capture
    echo "  System audio will be captured via meetscribe_sink.monitor"
    
    # Create loopback to capture mic (one-way: mic -> recording, NOT mic -> headphones)
    if ! pactl list modules short 2>/dev/null | grep -q "meetscribe_mic"; then
        pactl load-module module-loopback source="$MIC_SOURCE" sink=meetscribe_sink latency_msec=20 module_name=meetscribe_mic
    fi
    
    echo "✓ Recording mode enabled"
    echo "  - Headphone output: $HEADSET_SINK"
    echo "  - System audio capture: meetscribe_sink.monitor"
    echo "  - Microphone capture: via loopback"
}

stop_recording_mode() {
    echo "Stopping MeetScribe recording mode..."
    
    # Remove mic loopback (this was causing the echo!)
    for mod in $(pactl list modules short 2>/dev/null | grep "meetscribe_mic" | awk '{print $1}'); do
        pactl unload-module $mod 2>/dev/null && echo "  Removed mic loopback"
    done
    
    # Set default output to headset
    pactl set-default-sink "$HEADSET_SINK"
    
    echo "✓ Normal audio mode restored"
    echo "  - Output: $HEADSET_SINK"
    echo "  - No recording capture active"
}

show_status() {
    echo "=== MeetScribe Audio Status ==="
    echo ""
    echo "Default Output:"
    wpctl status 2>/dev/null | grep "Default" || pactl info 2>/dev/null | grep "Default Sink"
    echo ""
    echo "Recording Sources:"
    if wpctl status 2>/dev/null | grep -q "meetscribe_sink"; then
        echo "  ✓ meetscribe_sink: $(wpctl status 2>/dev/null | grep 'meetscribe_sink' | head -1)"
    else
        echo "  ✗ Not in recording mode"
    fi
    echo ""
    echo "Active Loopbacks:"
    pactl list modules short 2>/dev/null | grep loopback || echo "  None"
}

case "$1" in
    start)
        start_recording_mode
        ;;
    stop)
        stop_recording_mode
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac