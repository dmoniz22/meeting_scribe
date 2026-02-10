# TASK.md — MeetScribe Implementation Task Breakdown

> This is the coding agent's task list. Work through each phase in order.
> Mark items `[x]` as you complete them, `[/]` when in progress.

---

## Phase 1: The Foundation (Week 1-2)

- [ ] **1.1** Create monorepo structure: `backend/`, `frontend/`, `audio-daemon/`, `docker/`, `data/`
- [ ] **1.2** Write `docker-compose.yml` with services: `db`, `redis`, `api`, `worker`, `frontend`, `ollama`
- [ ] **1.3** Create PostgreSQL Dockerfile extending `pgvector/pgvector:pg17`
- [ ] **1.4** Initialize FastAPI project in `backend/` with `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `celery[redis]`, `pydantic`
- [ ] **1.5** Implement SQLAlchemy ORM models for all tables defined in IMPLEMENTATION.md §3
  - [ ] `users`, `meetings`, `speakers`, `transcript_segments`
  - [ ] `notes`, `summaries`, `calendar_connections`, `calendar_events`, `exports`
- [ ] **1.6** Set up Alembic and generate initial migration
- [ ] **1.7** Implement basic CRUD endpoints for `meetings` (create, list, get, update, delete)
- [ ] **1.8** Initialize Next.js 15 project with App Router, Tailwind CSS 4, Lucide Icons
- [ ] **1.9** Verify: `docker compose up` starts all services; `GET /api/v1/meetings` returns `[]`

---

## Phase 2: The Ear — Audio Capture (Week 3-4)

- [ ] **2.1** Write `setup_pipewire.sh`: creates `pw-loopback` virtual sink/source per IMPLEMENTATION.md §2.1
- [ ] **2.2** Implement `capture.py`: `sounddevice`-based capture from `meetscribe_source` at 16kHz stereo, writing 30s WAV chunks
- [ ] **2.3** Implement `device_monitor.py`: watch `pw-dump --monitor` for device changes, restart loopbacks
- [ ] **2.4** Add RMS level calculation to capture loop; publish to Redis `audio:levels:{meeting_id}`
- [ ] **2.5** Implement Audio Daemon HTTP server (Unix socket): `/start`, `/stop`, `/status`
- [ ] **2.6** Implement full recording lifecycle in API Server: call Audio Daemon → start/stop → concat chunks with `ffmpeg`
- [ ] **2.7** Implement WebSocket endpoint `/ws/meetings/{id}`: subscribe to Redis pub/sub, broadcast `audio_level` events
- [ ] **2.8** Write `meetscribe-audio.service` systemd unit file
- [ ] **2.9** Verify: API start → WAV chunks appear → audio levels stream → stop → full WAV created → headphone unplug recovers

---

## Phase 3: The Brain — AI Pipeline (Week 5-7)

- [ ] **3.1** Implement Celery task `transcribe_meeting`: load WhisperX with `large-v2`, `float16`, batch_size 8
- [ ] **3.2** Integrate pyannote diarization via WhisperX; assign `SPEAKER_XX` labels per segment
- [ ] **3.3** Implement sequential GPU processing: unload models between steps with `torch.cuda.empty_cache()`
- [ ] **3.4** Store WhisperX output: create `speakers` and `transcript_segments` records in PostgreSQL
- [ ] **3.5** Implement Celery task `generate_embeddings`: embed transcript segments and notes with `all-MiniLM-L6-v2` (384-dim)
- [ ] **3.6** Create HNSW indexes on `transcript_segments.embedding` and `notes.embedding`
- [ ] **3.7** Implement Celery task `summarize_meeting`: send transcript + notes to Ollama → store summary, action items, decisions
- [ ] **3.8** Add progress tracking: report job progress via Redis → WebSocket `processing_progress` events
- [ ] **3.9** Implement `POST /api/v1/search` with hybrid search (keyword GIN + semantic pgvector + RRF merge)
- [ ] **3.10** Verify: upload test WAV → correct transcript + speaker labels → embeddings stored → search returns results → summary generated

---

## Phase 4: The Face — Frontend (Week 8-10)

- [ ] **4.1** Build AppShell layout: sidebar nav (Dashboard, Calendar, Settings), header with search bar
- [ ] **4.2** Build Dashboard page (`/dashboard`): meeting list with status badges, duration, date, filters, grid/list toggle
- [ ] **4.3** Build Recording page (`/record`): "Start Recording" button, timer, audio VU meter (WebSocket), live notes panel
- [ ] **4.4** Build Note Editor component: Tiptap rich text, auto-captures `recording_offset`, note type dropdown
- [ ] **4.5** Build Meeting Detail page (`/meetings/[id]`): tabs for Transcript, Notes, Summary
- [ ] **4.6** Build Audio Player component: HTML5 audio with custom controls, seek-to-timestamp, playback speed
- [ ] **4.7** Implement speaker renaming: click label → inline edit → API call
- [ ] **4.8** Build Search page (`/search`): mode toggle, results with snippets and meeting links
- [ ] **4.9** Build Export dialog: format selection (MD/PDF/JSON), download trigger
- [ ] **4.10** Polish: responsive layout, dark mode, loading states, error boundaries
- [ ] **4.11** Verify: full user flow — record → note → stop → process → review → search → export

---

## Phase 5: The Assistant — Calendar & Production (Week 11-14)

- [ ] **5.1** Implement Google Calendar OAuth2 flow (scopes: `calendar.readonly`) with encrypted token storage (Fernet)
- [ ] **5.2** Implement Outlook Calendar OAuth2 flow via MSAL + Microsoft Graph API
- [ ] **5.3** Implement Celery Beat task: sync calendars every 5 min, upsert events into `calendar_events`
- [ ] **5.4** Implement auto-record scheduler: check every minute for events starting within 2 min, start/stop recording
- [ ] **5.5** Build Calendar UI page (`/calendar`): upcoming events list with auto-record toggles
- [ ] **5.6** Implement Markdown export: Jinja2 template rendering meeting data
- [ ] **5.7** Implement PDF export: Markdown → HTML → WeasyPrint with custom CSS
- [ ] **5.8** Implement JSON export: direct serialization
- [ ] **5.9** Build Settings page (`/settings`): Whisper model, Ollama model, auto-record defaults, theme
- [ ] **5.10** Add error handling: global error boundaries (frontend), Celery retry policies (max 3, exponential backoff)
- [ ] **5.11** Add structured JSON logging (`structlog`), health check endpoints for all services
- [ ] **5.12** Verify: connect Google Cal → events sync → auto-record fires → PDF export looks professional

---

## Post-MVP Enhancements (Backlog)

- [ ] Real-time streaming transcription during recording
- [ ] Transcript segment correction UI (edit misattributed speaker/text)
- [ ] Meeting templates and recurring meeting detection
- [ ] Slack/Notion integration for sharing summaries
- [ ] Multi-user support with authentication (JWT)
- [ ] Mobile-responsive PWA
- [ ] Sentiment analysis per speaker
- [ ] Topic clustering across meetings
