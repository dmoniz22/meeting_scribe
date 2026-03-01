#!/bin/bash
# MeetScribe - Complete Startup Script
# Starts Audio Daemon + Docker Compose with full verification

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIO_DAEMON_DIR="$SCRIPT_DIR/audio-daemon"
SOCKET_PATH="/tmp/meetscribe-audio.sock"
AUDIO_LOG="/tmp/audio-daemon.log"

echo "=========================================="
echo "  MeetScribe - Complete Startup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# ============================================
# STEP 1: Check Prerequisites
# ============================================
echo "Step 1: Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker not found. Please install Docker."
    exit 1
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

print_status "Docker is running"

# Check for virtual environment
if [ ! -d "$AUDIO_DAEMON_DIR/venv" ]; then
    print_warning "Virtual environment not found. Setting up..."
    cd "$AUDIO_DAEMON_DIR"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    print_status "Virtual environment created"
else
    print_status "Virtual environment exists"
fi

# ============================================
# STEP 2: Stop any existing processes
# ============================================
echo ""
echo "Step 2: Cleaning up existing processes..."

# Kill old audio daemon processes
pkill -f "python.*server.py" 2>/dev/null || true
sleep 1

# Remove old socket
if [ -S "$SOCKET_PATH" ]; then
    rm -f "$SOCKET_PATH"
    print_status "Removed old socket"
fi

# ============================================
# STEP 3: Start Audio Daemon
# ============================================
echo ""
echo "Step 3: Starting Audio Daemon..."

cd "$AUDIO_DAEMON_DIR"
source venv/bin/activate

# Verify dependencies
if ! python -c "import numpy" 2>/dev/null; then
    print_error "numpy not found in venv. Installing dependencies..."
    pip install -r requirements.txt
fi

# Start audio daemon in background with nohup
nohup python server.py > "$AUDIO_LOG" 2>&1 &
AUDIO_PID=$!

# Wait for socket to be created
echo "  Waiting for audio daemon to start..."
for i in {1..15}; do
    if [ -S "$SOCKET_PATH" ]; then
        print_status "Audio daemon started (PID: $AUDIO_PID)"
        break
    fi
    if ! ps -p $AUDIO_PID > /dev/null 2>&1; then
        print_error "Audio daemon failed to start. Check logs: $AUDIO_LOG"
        exit 1
    fi
    echo "    Attempt $i/15..."
    sleep 1
done

if [ ! -S "$SOCKET_PATH" ]; then
    print_error "Audio daemon socket not created. Check logs: $AUDIO_LOG"
    tail -20 "$AUDIO_LOG"
    exit 1
fi

# Test audio daemon API
if curl -s --unix-socket "$SOCKET_PATH" http://localhost/status > /dev/null 2>&1; then
    print_status "Audio daemon responding to API calls"
else
    print_warning "Audio daemon socket exists but API not responding yet"
fi

# ============================================
# STEP 4: Start Docker Compose
# ============================================
echo ""
echo "Step 4: Starting Docker Compose services..."

cd "$SCRIPT_DIR"
docker compose up -d

# Wait for services
echo "  Waiting for services to be ready..."
sleep 3

# Check API health
API_READY=false
for i in {1..20}; do
    if curl -s http://localhost:8003/health > /dev/null 2>&1 || \
       curl -s http://localhost:8003/ > /dev/null 2>&1; then
        print_status "API is responding"
        API_READY=true
        break
    fi
    echo "    Waiting for API... ($i/20)"
    sleep 2
done

if [ "$API_READY" = false ]; then
    print_warning "API may still be starting..."
fi

# ============================================
# STEP 5: Verify Everything
# ============================================
echo ""
echo "Step 5: Verification..."

# Check audio daemon
if [ -S "$SOCKET_PATH" ]; then
    print_status "Audio daemon socket: $SOCKET_PATH"
else
    print_error "Audio daemon socket missing"
fi

# Check audio daemon API
AUDIO_STATUS=$(curl -s --unix-socket "$SOCKET_PATH" http://localhost/status 2>/dev/null || echo "{}")
if [ "$AUDIO_STATUS" != "{}" ]; then
    print_status "Audio daemon API: responding"
else
    print_error "Audio daemon API: not responding"
fi

# Check running containers
RUNNING_CONTAINERS=$(docker ps --filter "name=meetscribe" --format "table {{.Names}}" | tail -n +2 | wc -l)
if [ "$RUNNING_CONTAINERS" -ge 4 ]; then
    print_status "Docker containers: $RUNNING_CONTAINERS running"
else
    print_warning "Docker containers: only $RUNNING_CONTAINERS running (expected 4+)"
    docker compose ps
fi

# ============================================
# STEP 6: Print Summary
# ============================================
echo ""
echo "=========================================="
echo "  MeetScribe is Ready!"
echo "=========================================="
echo ""
echo "📊 Dashboard:    http://localhost:3000"
echo "📚 API Docs:     http://localhost:8003/docs"
echo "🔧 API:          http://localhost:8003"
echo ""
echo "Services Status:"
echo "  • Audio Daemon: running (PID: $AUDIO_PID)"
echo "  • API Container: $(docker ps --filter "name=meetscribe-api" --format "{{.Status}}" || echo "checking...")"
echo "  • Database: $(docker ps --filter "name=meetscribe-db" --format "{{.Status}}" || echo "checking...")"
echo "  • Frontend: $(docker ps --filter "name=meetscribe-frontend" --format "{{.Status}}" || echo "checking...")"
echo ""
echo "Logs:"
echo "  Audio Daemon: tail -f $AUDIO_LOG"
echo "  Docker: cd $SCRIPT_DIR && docker compose logs -f"
echo ""
echo "Recording Test:"
echo "  curl -s --unix-socket $SOCKET_PATH http://localhost/status"
echo ""
echo "=========================================="
echo ""

# Keep script running until user exits (optional)
read -p "Press Enter to exit, or Ctrl+C to keep running..."
