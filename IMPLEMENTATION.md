# Implementation Plan: Local-First Linux Meeting Assistant
## "MeetScribe" — Bot-less Meeting Transcription & Intelligence

---

## Section 1: Component Topology

### 1.1 Service Architecture

The system is composed of **six** discrete services orchestrated via Docker Compose. Each service runs in its own container except the **Audio Daemon**, which runs directly on the host (necessary for PipeWire access).

```
┌─────────────────────────────────────────────────────────────────┐
│                        HOST (EndeavourOS)                       │
│                                                                 │
│  ┌──────────────────┐     ┌──────────────────────────────────┐  │
│  │  Audio Daemon     │     │         Docker Compose           │  │
│  │  (Python process) │     │                                  │  │
│  │                   │     │  ┌────────────┐ ┌─────────────┐ │  │
│  │  - PipeWire       │────▶│  │ FastAPI    │ │ Next.js 15  │ │  │
│  │    pw-loopback    │     │  │ Backend    │ │ Frontend    │ │  │
│  │  - sounddevice    │     │  │ :8000      │ │ :3000       │ │  │
│  │  - WAV writer     │     │  └─────┬──────┘ └──────┬──────┘ │  │
│  │  - Level monitor  │     │        │               │         │  │
│  └──────────────────┘     │  ┌─────▼──────┐ ┌──────▼──────┐ │  │
│         │                  │  │ PostgreSQL │ │   Redis     │ │  │
│         │ WAV files        │  │ 17 +       │ │ (Job Queue) │ │  │
│         ▼                  │  │ pgvector   │ │ :6379       │ │  │
│  /data/recordings/         │  │ :5432      │ └─────────────┘ │  │
│                            │  └────────────┘                  │  │
│                            │                                  │  │
│                            │  ┌────────────┐                  │  │
│                            │  │  Ollama    │                  │  │
│                            │  │  (LLM)    │                  │  │
│                            │  │  :11434   │                  │  │
│                            │  └────────────┘                  │  │
│                            └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Service Definitions

| Service | Technology | Runs In | Port | Purpose |
|---|---|---|---|---|
| **audio-daemon** | Python 3.12 + `sounddevice` | Host (systemd) | Unix socket | Captures PipeWire audio, writes WAV chunks |
| **api-server** | FastAPI + Uvicorn | Docker | 8000 | REST API + WebSocket server |
| **worker** | Celery + Redis | Docker | — | Async jobs: transcription, summarization, embeddings |
| **frontend** | Next.js 15 (App Router) | Docker | 3000 | Web dashboard |
| **db** | PostgreSQL 17 + pgvector 0.8+ | Docker | 5432 | Relational + vector storage |
| **redis** | Redis 7 | Docker | 6379 | Celery broker + pub/sub for WebSocket events |
| **ollama** | Ollama (GPU passthrough) | Docker | 11434 | Local LLM inference |

### 1.3 Data Flow

```
User speaks / Meeting audio plays
        │
        ▼
  PipeWire (pw-loopback virtual sink)
        │
        ▼
  Audio Daemon (sounddevice capture)
        │
        ├──▶ WAV chunk written to /data/recordings/{meeting_id}/
        │
        ├──▶ Audio levels sent via Redis pub/sub → WebSocket → Frontend
        │
        ▼
  (Meeting ends / User clicks Stop)
        │
        ▼
  Celery Task: transcribe_meeting
        │
        ├──▶ WhisperX (faster-whisper backend + pyannote diarization)
        │         │
        │         ├──▶ Transcript segments → PostgreSQL
        │         └──▶ Speaker labels → PostgreSQL
        │
        ▼
  Celery Task: generate_embeddings
        │
        └──▶ sentence-transformers/all-MiniLM-L6-v2
                  │
                  └──▶ 384-dim vectors → pgvector column
        │
        ▼
  Celery Task: summarize_meeting
        │
        └──▶ Ollama (Llama 3 / Mistral)
                  │
                  ├──▶ Summary text → PostgreSQL
                  ├──▶ Action items → PostgreSQL
                  └──▶ Key decisions → PostgreSQL
```

### 1.4 Communication Patterns

| From | To | Protocol | Purpose |
|---|---|---|---|
| Frontend | API Server | REST (HTTP) | CRUD operations, search, export |
| Frontend | API Server | WebSocket | Live audio levels, recording status, live transcript |
| Audio Daemon | API Server | REST (localhost) | Notify recording start/stop, send audio levels |
| Audio Daemon | Redis | Pub/Sub | Push audio level data for WebSocket broadcast |
| API Server | Redis | Celery | Enqueue async jobs |
| Worker | PostgreSQL | SQLAlchemy | Store transcripts, embeddings, summaries |
| Worker | Ollama | HTTP (REST) | LLM inference for summaries |
| API Server | PostgreSQL | SQLAlchemy/asyncpg | All data access |

---

## Section 2: Audio Engineering Strategy

### 2.1 The PipeWire Virtual Sink Strategy

The core challenge: capture **both** the system output (what the user hears in their headphones) **and** the microphone input, then merge them into a single stream for recording—without disrupting the user's actual audio experience.

#### Step 1: Create a Combined Virtual Sink

Use `pw-loopback` to create two loopback modules that route audio into a single virtual sink:

```bash
# 1. Create the virtual recording sink (the "combined" sink)
pw-loopback \
  --capture-props='media.class=Audio/Sink node.name=meetscribe_sink node.description="MeetScribe Recording Sink"' \
  --playback-props='media.class=Audio/Source node.name=meetscribe_source node.description="MeetScribe Recording Source"'
```

This creates:
- A **virtual sink** named `meetscribe_sink` — anything routed here becomes capturable.
- A **virtual source** named `meetscribe_source` — our Python process reads from this.

#### Step 2: Route System Audio Monitor into the Virtual Sink

```bash
# 2. Loopback the system output monitor into meetscribe_sink
pw-loopback \
  --capture-props='node.target=<output_device_name>.monitor stream.dont-remix=true' \
  --playback-props='node.target=meetscribe_sink stream.dont-remix=true'
```

This captures the **monitor** of the user's output device (headphones/speakers) without affecting what the user hears.

#### Step 3: Route Microphone into the Virtual Sink

```bash
# 3. Loopback the microphone into meetscribe_sink
pw-loopback \
  --capture-props='node.target=<microphone_name> stream.dont-remix=true' \
  --playback-props='node.target=meetscribe_sink stream.dont-remix=true'
```

#### Step 4: Python Captures from the Virtual Source

The Audio Daemon uses `sounddevice` to record from `meetscribe_source`:

- **Sample rate**: 16000 Hz (Whisper's native rate).
- **Channels**: 2 (stereo — left = system audio, right = mic). This preserves channel separation for better diarization.
- **Format**: 32-bit float, written to WAV.
- **Chunk duration**: 30-second WAV files for near-real-time pipeline potential.

### 2.2 Device Change Handling

When headphones are unplugged/plugged:

1. **WirePlumber** automatically updates the default output sink.
2. The `pw-loopback` modules targeting a **specific device** will break.
3. **Solution**: The Audio Daemon monitors PipeWire device events via `pw-dump --monitor`. When a device change is detected:
   - Kill existing `pw-loopback` processes.
   - Query new default devices via `pw-cli ls Node`.
   - Re-create loopback modules targeting the new devices.
   - Log the interruption with timestamp for transcript alignment.

### 2.3 Audio Level Monitoring

The Audio Daemon calculates RMS levels from the captured audio buffer every 100ms:
- Publish levels to Redis channel `audio:levels:{meeting_id}`.
- The API Server subscribes and broadcasts via WebSocket to the frontend.
- Frontend renders a simple VU meter / waveform visualization.

### 2.4 File Organization

```
/data/recordings/
  └── {meeting_id}/
      ├── chunk_000.wav      # 0:00 - 0:30
      ├── chunk_001.wav      # 0:30 - 1:00
      ├── ...
      └── full_recording.wav  # Concatenated after meeting ends
```

---

## Section 3: Database Schema Specification

### 3.1 Extensions Required

```sql
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 3.2 Table Definitions

#### `users`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT uuid_generate_v4() | User identifier |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | User email |
| `display_name` | VARCHAR(100) | NOT NULL | Display name |
| `preferences` | JSONB | DEFAULT '{}' | User settings (theme, default model, etc.) |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Account creation |

#### `meetings`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK, DEFAULT uuid_generate_v4() | Meeting identifier |
| `user_id` | UUID | FK → users.id, NOT NULL | Owner |
| `title` | VARCHAR(500) | NOT NULL, DEFAULT 'Untitled Meeting' | Meeting title |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'idle' | One of: `idle`, `recording`, `processing`, `completed`, `failed` |
| `started_at` | TIMESTAMPTZ | NULL | When recording started (epoch) |
| `ended_at` | TIMESTAMPTZ | NULL | When recording stopped |
| `duration_seconds` | INTEGER | NULL | Calculated duration |
| `audio_path` | VARCHAR(1000) | NULL | Path to full_recording.wav |
| `calendar_event_id` | UUID | FK → calendar_events.id, NULL | Linked calendar event |
| `tags` | TEXT[] | DEFAULT '{}' | User-defined tags |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Record creation |
| `updated_at` | TIMESTAMPTZ | DEFAULT NOW() | Last update |

**Indexes**: B-tree on `(user_id, started_at DESC)`, B-tree on `status`.

#### `speakers`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Speaker identifier |
| `meeting_id` | UUID | FK → meetings.id ON DELETE CASCADE | Parent meeting |
| `label` | VARCHAR(50) | NOT NULL | Auto-assigned (e.g., `SPEAKER_00`) |
| `display_name` | VARCHAR(100) | NULL | User-assigned name (e.g., "Alice") |
| `color` | VARCHAR(7) | NOT NULL | Hex color for UI display |

**Indexes**: B-tree on `meeting_id`.

#### `transcript_segments`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Segment identifier |
| `meeting_id` | UUID | FK → meetings.id ON DELETE CASCADE | Parent meeting |
| `speaker_id` | UUID | FK → speakers.id | Speaker |
| `start_time` | FLOAT | NOT NULL | Offset in seconds from meeting start |
| `end_time` | FLOAT | NOT NULL | Offset in seconds |
| `text` | TEXT | NOT NULL | Transcribed text |
| `confidence` | FLOAT | NULL | WhisperX confidence score |
| `embedding` | vector(384) | NULL | Sentence embedding |

**Indexes**:
- B-tree on `(meeting_id, start_time)` for ordered retrieval.
- HNSW on `embedding` using cosine distance: `CREATE INDEX idx_segments_embedding ON transcript_segments USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)`.
- GIN on `text` using `pg_trgm` for fuzzy text search.

#### `notes`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Note identifier |
| `meeting_id` | UUID | FK → meetings.id ON DELETE CASCADE | Parent meeting |
| `user_id` | UUID | FK → users.id | Author |
| `recording_offset` | FLOAT | NOT NULL | Seconds from meeting start |
| `content` | TEXT | NOT NULL | Note body (Markdown) |
| `note_type` | VARCHAR(20) | DEFAULT 'general' | One of: `general`, `action_item`, `decision`, `question` |
| `embedding` | vector(384) | NULL | Sentence embedding for search |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Creation time |

**Indexes**: B-tree on `(meeting_id, recording_offset)`, HNSW on `embedding`.

#### `summaries`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Summary identifier |
| `meeting_id` | UUID | FK → meetings.id ON DELETE CASCADE, UNIQUE | One summary per meeting |
| `summary_text` | TEXT | NOT NULL | LLM-generated summary |
| `action_items` | JSONB | DEFAULT '[]' | List of `{text, owner, due_date}` |
| `key_decisions` | JSONB | DEFAULT '[]' | List of `{text, context}` |
| `model_used` | VARCHAR(100) | NOT NULL | e.g., "llama3:8b" |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Generation time |

**Indexes**: UNIQUE on `meeting_id`.

#### `calendar_connections`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Connection identifier |
| `user_id` | UUID | FK → users.id | Owner |
| `provider` | VARCHAR(20) | NOT NULL | `google` or `outlook` |
| `access_token` | TEXT | NOT NULL | Encrypted OAuth access token |
| `refresh_token` | TEXT | NOT NULL | Encrypted OAuth refresh token |
| `token_expiry` | TIMESTAMPTZ | NOT NULL | Token expiration |
| `calendar_id` | VARCHAR(500) | NOT NULL | Provider-specific calendar ID |
| `auto_record` | BOOLEAN | DEFAULT false | Auto-record all events from this calendar |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Connection time |

**Indexes**: B-tree on `(user_id, provider)`.

#### `calendar_events`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Event identifier |
| `connection_id` | UUID | FK → calendar_connections.id ON DELETE CASCADE | Source calendar |
| `provider_event_id` | VARCHAR(500) | NOT NULL | Provider's event ID |
| `title` | VARCHAR(500) | NOT NULL | Event title |
| `start_time` | TIMESTAMPTZ | NOT NULL | Event start |
| `end_time` | TIMESTAMPTZ | NOT NULL | Event end |
| `attendees` | JSONB | DEFAULT '[]' | List of attendee emails/names |
| `meeting_url` | VARCHAR(1000) | NULL | Zoom/Meet/Teams link |
| `auto_record` | BOOLEAN | DEFAULT false | Override: auto-record this specific event |
| `synced_at` | TIMESTAMPTZ | DEFAULT NOW() | Last sync timestamp |

**Indexes**: B-tree on `(start_time)`, UNIQUE on `(connection_id, provider_event_id)`.

#### `exports`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | UUID | PK | Export identifier |
| `meeting_id` | UUID | FK → meetings.id ON DELETE CASCADE | Source meeting |
| `format` | VARCHAR(10) | NOT NULL | `markdown`, `pdf`, or `json` |
| `file_path` | VARCHAR(1000) | NOT NULL | Path to generated file |
| `created_at` | TIMESTAMPTZ | DEFAULT NOW() | Export time |

---

## Section 4: API Specification (REST + WebSockets)

### 4.1 REST Endpoints

All endpoints are prefixed with `/api/v1`. Responses use JSON.

---

#### Meetings

**`POST /api/v1/meetings`** — Create a new meeting record.
- Body: `{ "title": "Sprint Planning" }`
- Response: `201` with meeting object.

**`GET /api/v1/meetings`** — List meetings with filters.
- Query: `?status=completed&limit=20&offset=0&sort=-started_at&search=sprint`
- Response: `200` with paginated list.

**`GET /api/v1/meetings/{id}`** — Get full meeting details (includes summary, speakers, note count).
- Response: `200` with meeting object + nested summary.

**`PUT /api/v1/meetings/{id}`** — Update meeting metadata.
- Body: `{ "title": "Q1 Sprint Planning" }`
- Response: `200`.

**`DELETE /api/v1/meetings/{id}`** — Delete meeting and all related data (cascade).
- Response: `204`.

---

#### Recording Control

**`POST /api/v1/recordings/start`** — Start recording.
- Body: `{ "meeting_id": "uuid" }` (optional — creates meeting if omitted).
- Action: Signals Audio Daemon to begin capture. Sets meeting status to `recording`.
- Response: `200` with `{ "meeting_id": "uuid", "started_at": "ISO8601" }`.

**`POST /api/v1/recordings/stop`** — Stop recording.
- Body: `{ "meeting_id": "uuid" }`
- Action: Signals Audio Daemon to stop. Concatenates chunks. Enqueues transcription job.
- Response: `200` with `{ "meeting_id": "uuid", "duration_seconds": 3600 }`.

**`GET /api/v1/recordings/status`** — Get current recording state.
- Response: `200` with `{ "is_recording": true, "meeting_id": "uuid", "duration": 1234, "audio_device": "..." }`.

---

#### Transcript

**`GET /api/v1/meetings/{id}/transcript`** — Get all transcript segments.
- Query: `?speaker_id=uuid` (optional filter by speaker).
- Response: `200` with ordered list of segments.

**`PUT /api/v1/meetings/{id}/speakers/{speaker_id}`** — Rename a speaker.
- Body: `{ "display_name": "Alice" }`
- Response: `200`.

**`POST /api/v1/meetings/{id}/transcript/regenerate`** — Re-run transcription.
- Response: `202 Accepted` with job ID.

---

#### Notes

**`POST /api/v1/meetings/{id}/notes`** — Create a timestamped note.
- Body: `{ "content": "Discuss budget next week", "recording_offset": 932.5, "note_type": "action_item" }`
- Response: `201` with note object.

**`GET /api/v1/meetings/{id}/notes`** — Get all notes for a meeting.
- Response: `200` with ordered list by `recording_offset`.

**`PUT /api/v1/meetings/{id}/notes/{note_id}`** — Update note content.
- Response: `200`.

**`DELETE /api/v1/meetings/{id}/notes/{note_id}`** — Delete a note.
- Response: `204`.

---

#### Search

**`POST /api/v1/search`** — Hybrid search across all meetings.
- Body: `{ "query": "budget discussion Q1", "mode": "hybrid", "limit": 20 }`
- `mode` options: `keyword`, `semantic`, `hybrid` (default).
- Response: `200` with list of `{ meeting_id, segment_id, text, score, meeting_title, timestamp }`.

**Implementation**:
1. **Keyword**: `SELECT ... WHERE text ILIKE '%query%'` or GIN trigram index.
2. **Semantic**: Embed query via `all-MiniLM-L6-v2`, then `ORDER BY embedding <=> $query_vec LIMIT 20`.
3. **Hybrid**: Run both, merge results using Reciprocal Rank Fusion (RRF).

---

#### Calendar

**`GET /api/v1/calendar/auth/{provider}`** — Initiate OAuth2 flow.
- `provider`: `google` or `outlook`.
- Response: `302` redirect to provider's auth page.

**`GET /api/v1/calendar/auth/{provider}/callback`** — OAuth2 callback.
- Exchanges code for tokens, stores encrypted tokens.
- Response: `302` redirect to frontend settings page.

**`GET /api/v1/calendar/connections`** — List connected calendars.
- Response: `200` with list of connections.

**`DELETE /api/v1/calendar/connections/{id}`** — Disconnect a calendar.
- Response: `204`.

**`POST /api/v1/calendar/sync`** — Trigger manual sync of all calendars.
- Response: `202 Accepted`.

**`GET /api/v1/calendar/events`** — List upcoming cached events.
- Query: `?from=ISO8601&to=ISO8601`.
- Response: `200` with event list.

**`PUT /api/v1/calendar/events/{id}`** — Toggle auto-record for a specific event.
- Body: `{ "auto_record": true }`
- Response: `200`.

---

#### Export

**`POST /api/v1/meetings/{id}/export`** — Generate export.
- Body: `{ "format": "pdf" }`
- Response: `202 Accepted` with `{ "export_id": "uuid" }`.

**`GET /api/v1/exports/{id}/download`** — Download generated export file.
- Response: `200` with file stream (Content-Disposition header).

---

#### Jobs

**`GET /api/v1/jobs/{id}`** — Check status of an async job (transcription, summarization, export).
- Response: `200` with `{ "status": "processing", "progress": 65, "result": null }`.

---

### 4.2 WebSocket Specification

**Endpoint**: `ws://localhost:8000/ws/meetings/{meeting_id}`

#### Server → Client Events

```json
{ "event": "recording_status", "data": { "is_recording": true, "duration": 1234 } }
{ "event": "audio_level", "data": { "rms_system": 0.42, "rms_mic": 0.15, "timestamp": 1707500000 } }
{ "event": "transcript_partial", "data": { "text": "...", "speaker": "SPEAKER_01", "start_time": 120.5 } }
{ "event": "processing_progress", "data": { "job": "transcription", "progress": 65 } }
{ "event": "note_added", "data": { "id": "uuid", "content": "...", "recording_offset": 932.5 } }
```

#### Client → Server Messages

```json
{ "action": "add_note", "data": { "content": "Follow up on budget", "note_type": "action_item" } }
{ "action": "update_title", "data": { "title": "Sprint Planning Call" } }
```

---

## Section 5: Phased Implementation Roadmap

### Phase 1: The Foundation (Week 1-2)

**Goal**: Working project scaffold with database and basic API.

| Task | Details | Output |
|---|---|---|
| 1.1 Project structure | Create monorepo with `backend/`, `frontend/`, `audio-daemon/`, `docker/` | Directory tree |
| 1.2 Docker Compose | Define all services: `db`, `redis`, `api`, `worker`, `frontend`, `ollama` | `docker-compose.yml` |
| 1.3 PostgreSQL + pgvector | Dockerfile extending `postgres:17` with `pgvector` installed. Alembic for migrations. | DB container + initial migration |
| 1.4 FastAPI scaffolding | Project with `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `celery[redis]`, `pydantic`. Basic health check endpoint. | `backend/` runnable |
| 1.5 SQLAlchemy models | Implement all tables from Section 3 as SQLAlchemy ORM models. | `backend/models/` |
| 1.6 Alembic migrations | Generate initial migration from models. | `backend/alembic/` |
| 1.7 Basic CRUD endpoints | Meetings list, create, get, update, delete. | Working REST API |
| 1.8 Next.js scaffold | Initialize Next.js 15 with App Router, Tailwind CSS, Lucide Icons. | `frontend/` runnable |

**Validation**: `docker compose up` brings all services online. `GET /api/v1/meetings` returns empty list. Next.js renders a placeholder page.

---

### Phase 2: The Ear (Week 3-4)

**Goal**: Reliable audio capture from PipeWire with real-time level monitoring.

| Task | Details | Output |
|---|---|---|
| 2.1 PipeWire setup script | Shell script that creates `pw-loopback` virtual sink/source as described in Section 2. | `audio-daemon/setup_pipewire.sh` |
| 2.2 Audio capture module | Python module using `sounddevice` to capture from `meetscribe_source` at 16kHz stereo. Write 30s WAV chunks. | `audio-daemon/capture.py` |
| 2.3 Device monitor | Monitor PipeWire device changes via `pw-dump --monitor`. Auto-restart loopbacks on device change. | `audio-daemon/device_monitor.py` |
| 2.4 Level monitoring | Calculate RMS from audio buffer. Publish to Redis `audio:levels:{meeting_id}`. | Integrated into capture loop |
| 2.5 Daemon control API | Simple HTTP server (Flask/FastAPI) on Unix socket. Endpoints: `/start`, `/stop`, `/status`. | `audio-daemon/server.py` |
| 2.6 Recording lifecycle | API Server calls Audio Daemon to start/stop. Concatenate chunks into `full_recording.wav` using `ffmpeg`. | End-to-end recording flow |
| 2.7 WebSocket audio levels | API Server subscribes to Redis pub/sub, broadcasts levels via WebSocket. | Real-time levels in browser |
| 2.8 systemd unit file | Unit file for the Audio Daemon with auto-restart. | `audio-daemon/meetscribe-audio.service` |

**Validation**: Start recording from API. Verify WAV files appear. Audio levels stream to WebSocket client. Stop recording produces concatenated file. Headphone unplug/replug recovers gracefully.

---

### Phase 3: The Brain (Week 5-7)

**Goal**: Transcription, diarization, embedding generation, and summarization pipeline.

| Task | Details | Output |
|---|---|---|
| 3.1 WhisperX integration | Celery task that loads `whisperx` with `faster-whisper` backend, model `large-v2`, compute type `float16`, batch size 8. | `backend/tasks/transcribe.py` |
| 3.2 Diarization | Use WhisperX's built-in pyannote diarization (requires HuggingFace token for `pyannote/speaker-diarization-3.1`). Assign speaker labels per segment. | Segments with speaker IDs |
| 3.3 VRAM management | **Sequential processing**: Unload WhisperX model after transcription, then load diarization model, then unload before Ollama. Use `torch.cuda.empty_cache()`. | GPU memory stays under 12GB |
| 3.4 Transcript storage | Parse WhisperX output. Create `speakers` and `transcript_segments` records. | Data in PostgreSQL |
| 3.5 Embedding generation | Celery task using `sentence-transformers/all-MiniLM-L6-v2` (384-dim). Embed each transcript segment and note. Store in `embedding` column. | pgvector populated |
| 3.6 HNSW index | Create HNSW index on `transcript_segments.embedding` and `notes.embedding` with `m=16, ef_construction=64`. | Fast vector search |
| 3.7 Summarization | Celery task that sends transcript + notes to Ollama (`llama3:8b`). Three prompts: summary, action items, key decisions. Store in `summaries` table. | LLM-generated intelligence |
| 3.8 Job progress tracking | Track progress in Redis. Broadcast via WebSocket (`processing_progress` events). | User sees "Transcribing... 65%" |
| 3.9 Hybrid search | Implement `POST /api/v1/search` with keyword (trigram GIN) + semantic (pgvector cosine) + RRF merging. | Working search endpoint |

**Validation**: Upload a test WAV file. Verify transcript segments with correct speaker labels. Search returns relevant results. Summary accurately captures meeting content.

---

### Phase 4: The Face (Week 8-10)

**Goal**: Full-featured Next.js frontend with live recording and meeting review.

| Task | Details | Output |
|---|---|---|
| 4.1 App layout | AppShell with sidebar navigation (Dashboard, Calendar, Settings). Global search bar in header. | Layout components |
| 4.2 Dashboard page | Meeting list with status badges, duration, date. Filters by status/date/tags. Grid + list toggle. | `/dashboard` |
| 4.3 Recording page | Big "Start Recording" button. Active recording shows: timer, audio VU meter (WebSocket), live notes panel. | `/record` |
| 4.4 Note editor | Rich text input (use `@tiptap/react`). On submit: captures current `recording_offset` from timer. Shows notes list with timestamps. | Component in recording page |
| 4.5 Meeting detail page | Tabs: Transcript, Notes, Summary. Transcript shows speaker-labeled segments with timestamps. Click timestamp to seek audio. | `/meetings/[id]` |
| 4.6 Audio player | HTML5 audio player with custom controls. Seek to timestamp on note/segment click. Playback speed control. | Reusable component |
| 4.7 Speaker renaming | Click speaker label → inline edit → `PUT /speakers/{id}`. Color-coded labels. | In transcript view |
| 4.8 Search page | Search input with mode toggle (keyword/semantic/hybrid). Results show snippet, meeting title, timestamp. Click to jump into meeting. | `/search` |
| 4.9 Export dialog | Modal with format selection (MD/PDF/JSON). Download on completion. | In meeting detail |
| 4.10 Responsive design | Tailwind responsive utilities. Mobile-friendly layout. Dark mode. | Polished UI |

**Validation**: Full user flow: Start recording → take notes → stop → wait for processing → review transcript with synced notes → search → export.

---

### Phase 5: The Assistant (Week 11-14)

**Goal**: Calendar automation, advanced features, production hardening.

| Task | Details | Output |
|---|---|---|
| 5.1 Google Calendar OAuth | OAuth2 flow using `google-auth-oauthlib`. Scopes: `calendar.readonly`. Store encrypted tokens (Fernet). | `/settings/calendar` |
| 5.2 Outlook Calendar OAuth | OAuth2 via MSAL (`msal` library). Microsoft Graph API. | `/settings/calendar` |
| 5.3 Calendar sync | Celery Beat periodic task (every 5 min). Fetch events for next 24h. Upsert into `calendar_events`. | Auto-synced events |
| 5.4 Auto-record scheduler | Celery Beat checks every minute for events starting within 2 min. If `auto_record=true`, start recording. Stop when event ends. | Hands-free recording |
| 5.5 Calendar UI | Calendar page showing upcoming events with auto-record toggles. | `/calendar` |
| 5.6 Markdown export | Jinja2 template rendering meeting data into clean Markdown. | `.md` file download |
| 5.7 PDF export | Render Markdown to HTML, then use `WeasyPrint` to generate styled PDF. Custom CSS for professional layout. | `.pdf` file download |
| 5.8 JSON export | Direct serialization of meeting data. | `.json` file download |
| 5.9 Settings page | Configuration for: default Whisper model, Ollama model, auto-record defaults, theme. | `/settings` |
| 5.10 Error handling | Global error boundaries (frontend). Retry policies for failed Celery tasks (max 3 retries, exponential backoff). | Resilient system |
| 5.11 Logging & monitoring | Structured JSON logging (`structlog`). Log rotation. Health check endpoints for all services. | Observability |

**Validation**: Connect Google Calendar. Verify events sync. Set auto-record on an event. Confirm recording starts/stops automatically. Export a meeting as PDF and verify formatting.

---

## Section 6: Risk Analysis

### Risk 1: GPU VRAM Exhaustion

**Problem**: WhisperX `large-v2` needs ~8GB VRAM. Pyannote diarization adds ~2-6GB. Ollama `llama3:8b` needs ~6GB. Running simultaneously would exceed most consumer GPUs.

**Mitigation (Prescriptive)**:
1. **Sequential GPU processing**: Never run two GPU-heavy tasks concurrently. The Celery worker processes steps in strict order: Transcribe → Unload → Diarize → Unload → Embed → Summarize.
2. **Explicit model unloading**: After each step, call `del model; torch.cuda.empty_cache(); gc.collect()`.
3. **Ollama model management**: Use `ollama` API to unload models when not in use (`POST /api/generate` with `keep_alive=0`).
4. **Configurable model sizes**: Allow users to select `medium` or `small` Whisper models (4GB / 2GB VRAM) in settings.
5. **CPU fallback**: If no GPU is detected, use `compute_type=int8` on CPU. Slower but functional.

**Minimum GPU**: NVIDIA GPU with 8GB VRAM (e.g., RTX 3060).
**Recommended GPU**: 12GB+ VRAM (e.g., RTX 3060 12GB, RTX 4070).

### Risk 2: Audio Drift Over Long Meetings

**Problem**: Two separate `pw-loopback` streams (system audio + mic) may drift apart over a 1-2 hour meeting due to different clock domains.

**Mitigation**:
1. **Single virtual sink approach**: Both streams are mixed into `meetscribe_sink` by PipeWire itself (which handles resampling/clock sync internally). The Python daemon captures the **already-mixed** output — a single stream with no drift.
2. **PipeWire's internal resampler**: PipeWire uses `spa-resample` to align streams to a common clock. This is handled at the graph level before our capture point.
3. **Monitoring**: Log timestamps at chunk boundaries. If inter-chunk gaps exceed 50ms, log a warning.

### Risk 3: PipeWire Permissions & Stability

**Problem**: The Audio Daemon runs as a user-level service but needs access to PipeWire's runtime socket.

**Mitigation**:
1. **Run as the user**: The systemd unit uses `User=%I` (user service), which inherits PipeWire socket access via `XDG_RUNTIME_DIR`.
2. **PipeWire health check**: Before starting capture, verify PipeWire is running via `pw-cli info 0`. If not, wait and retry.
3. **Watchdog**: The daemon monitors its own capture thread. If no audio data arrives for 10 seconds during recording, kill and restart loopbacks.

### Risk 4: Calendar Token Security

**Problem**: OAuth tokens stored in PostgreSQL could be compromised if the database is accessed.

**Mitigation**:
1. **Encryption at rest**: Use Python `cryptography.fernet` to encrypt `access_token` and `refresh_token` before storage. Encryption key stored in environment variable, never in DB.
2. **Minimal scopes**: Request only `calendar.readonly` (Google) / `Calendars.Read` (Microsoft).
3. **Token rotation**: Refresh tokens automatically before expiry. Delete tokens on calendar disconnect.

### Risk 5: Diarization Accuracy

**Problem**: Pyannote diarization can produce incorrect speaker labels, especially with overlapping speech or similar voices.

**Mitigation**:
1. **Stereo channel separation**: By recording system audio on left channel and mic on right channel, we know the **local user** is predominantly on the right channel. Use this as a strong prior for speaker assignment.
2. **User relabeling**: The UI provides easy speaker renaming. Labels persist across the meeting.
3. **Min/max speakers config**: Allow users to specify expected number of speakers (2-10) to constrain diarization.
4. **Post-hoc correction**: Future enhancement — allow users to correct misattributed segments via UI.

### Risk 6: Large Meeting Processing Time

**Problem**: A 2-hour meeting produces ~230MB of WAV audio. WhisperX `large-v2` processes at ~70x real-time on GPU, so a 2-hour file takes ~2 minutes. But diarization and embedding can add significant time.

**Mitigation**:
1. **Progress reporting**: The Celery task reports progress via Redis → WebSocket. The user sees a progress bar.
2. **Chunked processing**: Process audio in 10-minute chunks for WhisperX to reduce memory footprint.
3. **Background processing**: All heavy computation runs in the Celery worker. The API and frontend remain responsive.
4. **Priority queue**: Use separate Celery queues: `high` (recording control), `default` (transcription), `low` (embedding, export).

---

## Appendix A: Technology Versions

| Technology | Version | Installation |
|---|---|---|
| Python | 3.12+ | System / pyenv |
| Node.js | 20 LTS | nvm |
| PostgreSQL | 17 | Docker: `postgres:17` |
| pgvector | 0.8+ | Docker: `pgvector/pgvector:pg17` |
| Redis | 7 | Docker: `redis:7-alpine` |
| WhisperX | Latest | pip: `whisperx` |
| faster-whisper | 1.0+ | pip (dependency of whisperx) |
| pyannote.audio | 3.1+ | pip (dependency of whisperx) |
| Ollama | Latest | Docker: `ollama/ollama` |
| sentence-transformers | 3.0+ | pip |
| FastAPI | 0.115+ | pip |
| SQLAlchemy | 2.0+ | pip: `sqlalchemy[asyncio]` |
| Celery | 5.4+ | pip: `celery[redis]` |
| Next.js | 15 | npx: `create-next-app` |
| Tailwind CSS | 4.0 | npm |
| Tiptap | 2.x | npm: `@tiptap/react` |
| WeasyPrint | 62+ | pip (+ system deps: `pango`, `cairo`) |
| sounddevice | 0.5+ | pip (+ system dep: `portaudio`) |

## Appendix B: Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://meetscribe:password@db:5432/meetscribe

# Redis
REDIS_URL=redis://redis:6379/0

# Audio
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=2
AUDIO_CHUNK_SECONDS=30
RECORDINGS_PATH=/data/recordings

# AI/ML
WHISPER_MODEL=large-v2
WHISPER_COMPUTE_TYPE=float16
WHISPER_BATCH_SIZE=8
HF_TOKEN=hf_xxxxx  # Required for pyannote diarization model
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=llama3:8b
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Calendar
GOOGLE_CLIENT_ID=xxxxx
GOOGLE_CLIENT_SECRET=xxxxx
OUTLOOK_CLIENT_ID=xxxxx
OUTLOOK_CLIENT_SECRET=xxxxx
CALENDAR_SYNC_INTERVAL_MINUTES=5

# Security
ENCRYPTION_KEY=xxxxx  # Fernet key for token encryption
SECRET_KEY=xxxxx      # FastAPI session/JWT secret

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```
