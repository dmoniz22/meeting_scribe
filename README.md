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
   - API: http://localhost:8000/docs
   - Frontend: http://localhost:3000
   - API Health: `curl http://localhost:8000/health`

### Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Next.js web dashboard |
| API | http://localhost:8000 | FastAPI REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Database | localhost:5432 | PostgreSQL 17 + pgvector |
| Redis | localhost:6379 | Job queue |
| Ollama | http://localhost:11434 | Local LLM inference |

### Default Credentials

- **Database:** meetscribe / Birdsey5@
- **PostgreSQL:** User: meetscribe, Password: Birdsey5@

### Audio Daemon Setup

The Audio Daemon runs on the host (not in Docker) to access PipeWire:

1. **Check if PipeWire is installed:**
   ```bash
   pipewire --version
   pw-cli info 0
   ```

2. **Install Audio Daemon dependencies:**
   ```bash
   # On Arch/EndeavourOS
   sudo pacman -S python-sounddevice portaudio
   
   # Install Python dependencies
   cd audio-daemon
   pip install -r requirements.txt
   ```

3. **Run the Audio Daemon:**
   ```bash
   cd audio-daemon
   python server.py
   ```

4. **Or install as systemd service:**
   ```bash
   sudo cp meetscribe-audio.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable meetscribe-audio.service
   sudo systemctl start meetscribe-audio.service
   ```

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
├── docker/            # Docker configurations
├── data/              # Persistent data
└── docker-compose.yml
```

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

## License

MIT
