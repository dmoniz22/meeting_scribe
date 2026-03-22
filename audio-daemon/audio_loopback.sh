#!/bin/bash
# Audio loopback with recording - captures mic and plays to headphones while recording

# Configuration
MIC_SOURCE="default"
OUTPUT_SINK="alsa_output.usb-Logitech_Logi_USB_Headset_000000000000-00.iec958-stereo"
RECORDING_FILE="$1"

if [ -z "$RECORDING_FILE" ]; then
    RECORDING_FILE="/tmp/meetscribe_loopback_$(date +%s).wav"
fi

echo "Starting audio loopback with recording..."
echo "Recording to: $RECORDING_FILE"

# Use FFmpeg to:
# 1. Read from PulseAudio (microphone)
# 2. Output to both: file (recording) AND headphones (so you can hear)
ffmpeg -f pulse -i "$MIC_SOURCE" \
    -f wav -acodec pcm_s16le "$RECORDING_FILE" \
    -f pulse -i "$OUTPUT_SINK" -async 1 \
    -f pulse "$OUTPUT_SINK" &

FFMPEG_PID=$!
echo "FFmpeg PID: $FFMPEG_PID"

# Save PID for later stopping
echo $FFMPEG_PID > /tmp/meetscribe_loopback.pid

# Keep running
wait $FFMPEG_PID
