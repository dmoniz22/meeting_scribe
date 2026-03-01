# MeetScribe - Local-First Linux Meeting Assistant

A bot-less meeting transcription and intelligence platform built with FastAPI, Next.js, PostgreSQL, and Ollama.

## Quick Start

### Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with CUDA support (RTX 4080 12GB recommended)
- PipeWire (for audio capture)
- Linux (EndeavourOS/Arch-based)

### Initial Setup

1. **Clone and enter the repository:**
   ```bash
   git clone git@github.com:dmoniz22/meeting_scribe.git
   cd meeting_scribe
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Start the services:**
   ```bash
   docker compose up -d
   ```

4. **Pull the Ollama model:**
   ```bash
   docker compose exec ollama ollama pull llama3.1:8b
   ```

5. **Verify the installation:**
   - API: http://localhost:8003/docs
   - Frontend: http://localhost:3000
   - API Health: `curl http://localhost:8003/health`

### Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Next.js web dashboard |
| API | http://localhost:8003 | FastAPI REST API |
| API Docs | http://localhost:8003/docs | Swagger UI |
| Database | localhost:5432 | PostgreSQL 17 + pgvector |
| Redis | localhost:6379 | Job queue & pub/sub |
| Ollama | http://localhost:11434 | Local LLM inference |

### Default Credentials

- **Database:** meetscribe / Birdsey5@
- **PostgreSQL:** User: meetscribe, Password: Birdsey5@

## Audio Recording Setup

### Prerequisites

1. **Check if PipeWire is installed:**
   ```bash
   pipewire --version
   pw-cli info 0
   ```

2. **If PipeWire is not installed (Arch/EndeavourOS):**
   ```bash
   sudo pacman -S pipewire pipewire-pulse wireplumber
   systemctl --user enable --now pipewire pipewire-pulse wireplumber
   ```

### Audio Daemon Setup

The Audio Daemon runs on the host (not in Docker) to access PipeWire:

1. **Install Audio Daemon dependencies:**
   ```bash
   # On Arch/EndeavourOS
   sudo pacman -S python-sounddevice portaudio
   
   # Create virtual environment and install dependencies
   cd audio-daemon
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Set up PipeWire virtual sink (creates the recording device):**
   ```bash
   cd audio-daemon
   ./setup_pipewire.sh
   ```
   
   This creates:
   - `MeetScribe Recording Sink` - Virtual sink that mixes system audio + mic
   - `MeetScribe Recording Source` - Virtual source for the app to capture from
   - Routes system audio to Left channel, microphone to Right channel

3. **Run the Audio Daemon:**
   ```bash
   cd audio-daemon
   source venv/bin/activate
   python server.py
   ```

4. **Or install as systemd service:**
   ```bash
   sudo cp audio-daemon/meetscribe-audio.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable meetscribe-audio.service --user
   sudo systemctl start meetscribe-audio.service --user
   ```

### Testing Audio Recording

1. **Start a recording:**
   ```bash
   curl -X POST http://localhost:8003/api/v1/recordings/start \
     -H "Content-Type: application/json" \
     -d '{"meeting_id": null}'
   ```

2. **Check recording status:**
   ```bash
   curl http://localhost:8003/api/v1/recordings/status
   ```

3. **Stop the recording:**
   ```bash
   curl -X POST http://localhost:8003/api/v1/recordings/stop
   ```

4. **Files are saved to:** `./data/recordings/{meeting_id}/`
   - `chunk_000.wav`, `chunk_001.wav`, etc. (30-second chunks)
   - `full_recording.wav` (concatenated after stop)

## Project Structure

```
meeting_scribe/
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── models/    # SQLAlchemy models
│   │   ├── routers/   # API endpoints
│   │   ├── services/  # Business logic
│   │   └── core/      # Config, database
│   └── alembic/       # Database migrations
├── frontend/          # Next.js 15 application
├── audio-daemon/      # PipeWire audio capture (host)
│   ├── setup_pipewire.sh     # Virtual sink setup
│   ├── capture.py            # Audio capture module
│   ├── device_monitor.py     # Device change detection
│   ├── server.py             # HTTP control server
│   └── meetscribe-audio.service  # systemd unit
├── docker/            # Docker configurations
├── data/              # Persistent data
└── docker-compose.yml
```

## API Endpoints

### Meetings
- `GET /api/v1/meetings` - List meetings
- `POST /api/v1/meetings` - Create meeting
- `GET /api/v1/meetings/{id}` - Get meeting details
- `PUT /api/v1/meetings/{id}` - Update meeting
- `DELETE /api/v1/meetings/{id}` - Delete meeting

### Recording
- `POST /api/v1/recordings/start` - Start recording
- `POST /api/v1/recordings/stop` - Stop recording
- `GET /api/v1/recordings/status` - Get recording status

### WebSocket
- `WS /ws/meetings/{meeting_id}` - Real-time audio levels and events

## Development

### Backend Development

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Audio Daemon Development

```bash
cd audio-daemon
source venv/bin/activate
python capture.py --duration 10 --concatenate  # Test capture
python device_monitor.py                       # Test device monitoring
python server.py                              # Run the full daemon
```

### Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Configuration

Edit `.env` file to customize:

- `WHISPER_MODEL`: whisper model (medium, large-v2, etc.)
- `OLLAMA_MODEL`: LLM model (llama3.1:8b, etc.)
- `WHISPER_COMPUTE_TYPE`: float16, int8, etc.
- `HF_TOKEN`: HuggingFace token for pyannote diarization

## Audio Architecture

```
System Output (speakers/headphones)
    ↓ (monitor)
MeetScribe Virtual Sink (mixes audio)
    ↓
MeetScribe Virtual Source (capture device)
    ↓
Audio Daemon → WAV chunks → FFmpeg concat

Microphone Input
    ↓
MeetScribe Virtual Sink
```

**Channel Layout:**
- Left Channel: System audio (what you hear)
- Right Channel: Microphone (what you say)

This stereo separation helps with speaker diarization in Phase 3.

## License

MIT
