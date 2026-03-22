#!/bin/bash
#
# install.sh - Install MeetScribe audio routing automation
#
# This script:
# 1. Symlinks the systemd user service
# 2. Enables the routing to start on login
# 3. Runs initial setup
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

AUDIO_DIR="$HOME/projects/meeting_transcriber/audio-daemon"
SYSTEMD_DIR="$HOME/.config/systemd/user"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}MeetScribe Audio Routing Installer${NC}"
echo "===================================="

# Check if we're in the right directory
if [ ! -f "$AUDIO_DIR/setup_pipewire_easyeffects.sh" ]; then
    echo -e "${RED}Error: Not in audio-daemon directory${NC}"
    echo "Run from: ~/projects/meeting_transcriber/audio-daemon/"
    exit 1
fi

# 1. Create systemd user directory
echo -e "\n${YELLOW}Step 1: Setting up systemd user service...${NC}"
mkdir -p "$SYSTEMD_DIR"
if [ -f "$AUDIO_DIR/meetscribe-audio-routing.service" ]; then
    ln -sf "$AUDIO_DIR/meetscribe-audio-routing.service" "$SYSTEMD_DIR/"
    echo -e "${GREEN}✓ Service file linked${NC}"
else
    echo -e "${YELLOW}⚠ Service file not found, skipping${NC}"
fi

# 2. Enable systemd user service
echo -e "\n${YELLOW}Step 2: Enabling auto-start service...${NC}"
if command -v systemctl &> /dev/null; then
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user enable meetscribe-audio-routing.service 2>/dev/null && \
        echo -e "${GREEN}✓ Service enabled${NC}" || \
        echo -e "${YELLOW}⚠ Could not enable service (may need to start manually first)${NC}"
else
    echo -e "${YELLOW}⚠ systemctl not available${NC}"
fi

# 3. Run initial setup
echo -e "\n${YELLOW}Step 3: Running initial audio setup...${NC}"
chmod +x "$AUDIO_DIR/setup_pipewire_easyeffects.sh"
"$AUDIO_DIR/setup_pipewire_easyeffects.sh"

echo -e "\n${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Installation complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}The audio routing will now start automatically on login.${NC}"
echo ""
echo -e "${YELLOW}To manually control the service:${NC}"
echo "  systemctl --user start meetscribe-audio-routing   # Start routing"
echo "  systemctl --user stop meetscribe-audio-routing    # Stop routing"
echo "  systemctl --user status meetscribe-audio-routing  # Check status"
echo ""
echo -e "${YELLOW}Or run the setup script directly:${NC}"
echo "  cd ~/projects/meeting_transcriber/audio-daemon"
echo "  ./setup_pipewire_easyeffects.sh"
echo ""
echo -e "${YELLOW}Then start the audio daemon:${NC}"
echo "  ./start_audio.sh"
