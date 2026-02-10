# Prompt for Claude Opus 4.6 (Thinking) — System Architect for Linux‑Native Meeting Assistant

You are Claude Opus 4.6 (thinking mode), acting as a senior software architect and systems designer.

Your task is to produce a **comprehensive, deeply detailed implementation plan** for a self‑hosted, Linux‑native meeting assistant web application. This plan will be handed to a separate “coding agent” whose sole responsibility will be to implement what you design. Therefore, your output must be:

- Exhaustive in architecture and design details  
- Clear, structured, and unambiguous  
- Completely free of code (no code snippets, no pseudocode)  
- Focused on concrete implementation steps, components, and data structures  

You are not allowed to write any code. Your job is to think, design, and specify.

---

## 1. Context and Goals

The user runs EndeavourOS (Arch‑based Linux) with strong hardware (including a powerful GPU) and already uses tools like Docker/Podman, FastAPI, Postgres, and local LLMs (e.g., via Ollama or similar). They want a **Granola‑style** meeting assistant that:

- Runs locally on Linux  
- Captures audio passively (no bot joining calls)  
- Transcribes and diarizes meetings  
- Allows live note‑taking during meetings  
- Generates summaries and action items  
- Integrates with calendars to auto‑start recordings  
- Provides a web dashboard for managing and searching meetings  
- Supports export to Markdown and PDF  
- Uses Postgres with pgvector for semantic search  

Your job is to design this system end‑to‑end.

---

## 2. High‑Level Product Description

Design a full‑stack web application that provides:

1. Passive audio capture of system audio and microphone on Linux, even when using headphones, via PipeWire or equivalent.
2. Meeting lifecycle management: start/stop recording manually or automatically via calendar events.
3. Transcription of recorded audio using a local model such as WhisperX or faster‑whisper, with GPU acceleration.
4. Speaker diarization: identify and label different speakers in the transcript.
5. Live note‑taking during meetings, with automatic timestamps aligned to the meeting timeline.
6. Automatic generation of:
   - Meeting summaries  
   - Key decisions  
   - Action items (with owners and optional due dates)  
7. Calendar integration:
   - Google Calendar  
   - Microsoft Outlook / Microsoft 365  
   - Ability to mark events as “auto‑record”  
8. A web dashboard:
   - List of past meetings  
   - Meeting detail pages (transcript, notes, summary, action items, audio playback)  
   - Search across meetings (keyword and semantic search)  
9. Export capabilities:
   - Export meeting content to Markdown  
   - Export meeting content to PDF  
10. All data stored in Postgres, with pgvector used for embeddings and semantic search.

The system should be modular, maintainable, and designed for future multi‑user support, even if initial implementation is single‑user.

---

## 3. Functional Requirements (Detailed)

You must expand and refine these into a precise, implementable specification.

### 3.1 Meeting Recording and Audio Capture

- The system must:
  - Capture system audio and microphone audio passively on Linux using PipeWire or equivalent.
  - Work even when the user is using headphones.
  - Allow the user to manually start and stop recording from the web UI.
  - Automatically start and stop recording based on calendar events.
  - Store audio files per meeting with appropriate metadata (e.g., format, duration, sample rate).
- The architect should:
  - Describe how to configure and use a PipeWire monitor or similar mechanism to capture mixed audio.
  - Describe how the backend will control the audio capture process (start, stop, error handling).
  - Define how audio files are named, stored, and linked to meeting records.

### 3.2 Transcription

- The system must:
  - Use a local transcription engine (e.g., WhisperX or faster‑whisper) with GPU acceleration.
  - Support batch transcription after recording ends (real‑time transcription is optional but can be considered).
  - Produce transcripts with timestamps at the segment level.
- The architect should:
  - Define how audio files are passed to the transcription service.
  - Define how transcription jobs are queued, processed, and monitored.
  - Define the structure of transcript segments (e.g., start time, end time, text, speaker label).
  - Describe how to handle long recordings (chunking, memory considerations, etc.).

### 3.3 Speaker Diarization

- The system must:
  - Perform speaker diarization so that each transcript segment is associated with a speaker label (e.g., SPEAKER_00, SPEAKER_01).
  - Allow the user to rename speakers in the UI (e.g., SPEAKER_00 → “Alice”).
- The architect should:
  - Describe how diarization is integrated into the transcription pipeline (e.g., via WhisperX with diarization support).
  - Define a data model for speakers and their mapping to segments.
  - Describe how speaker renaming is stored and applied in the UI.

### 3.4 Note‑Taking

- The system must:
  - Provide a live note‑taking interface in the web app during an active meeting.
  - Automatically timestamp each note relative to the meeting start time.
  - Store notes in the database and associate them with the corresponding meeting.
  - Allow notes to be displayed alongside the transcript in the meeting detail view.
- The architect should:
  - Describe how the frontend will handle live note entry and timestamping.
  - Define the data model for notes.
  - Describe how notes are merged or aligned with transcript segments in the UI and in summaries.

### 3.5 Summaries, Decisions, and Action Items

- The system must:
  - Use a local LLM (e.g., via Ollama, OpenClaw, or similar) to generate:
    - A concise meeting summary  
    - A list of key decisions  
    - A list of action items, ideally with owners and optional due dates  
  - Use both the transcript and the user’s notes as input to the LLM.
- The architect should:
  - Define the prompts conceptually (without writing actual prompt text) for:
    - Summary generation  
    - Decision extraction  
    - Action item extraction  
  - Describe how the summarization pipeline is triggered (e.g., after transcription completes).
  - Define how summaries, decisions, and action items are stored in the database.
  - Describe how embeddings are generated for semantic search (e.g., using the same or a different model).

### 3.6 Calendar Integration and Auto‑Recording

- The system must:
  - Integrate with Google Calendar and Microsoft Outlook / Microsoft 365.
  - Use OAuth2 for authentication and token management.
  - Periodically sync upcoming events.
  - Store calendar events in the database.
  - Allow the user to mark events (or entire calendars) as “auto‑record”.
  - Automatically create a meeting record and start recording when an event’s start time is reached.
- The architect should:
  - Describe the OAuth2 flow for each provider.
  - Define the data model for calendars and calendar events.
  - Describe the sync strategy (polling, webhooks, or both).
  - Describe the scheduling mechanism that checks for upcoming events and triggers recording.
  - Describe how to handle time zones, event updates, cancellations, and overlapping events.

### 3.7 Dashboard and Web UI

- The system must provide:
  - A dashboard listing all meetings with key metadata (title, date, duration, status, summary presence).
  - Filters and search (by date, title, tags, etc.).
  - A meeting detail page showing:
    - Title, date, duration, calendar link (if any)
    - Audio playback
    - Transcript with speaker labels
    - Notes (aligned by time)
    - Summary
    - Decisions
    - Action items
  - A live meeting page showing:
    - Recording status
    - Timer
    - Live notes panel
- The architect should:
  - Describe the overall UI layout and navigation structure.
  - Describe how the live meeting view interacts with the backend (e.g., polling, websockets, or simple form posts).
  - Describe how transcript and notes are presented and aligned.
  - Describe how speaker renaming is handled in the UI.

### 3.8 Search and pgvector Integration

- The system must:
  - Support keyword search across meetings, transcripts, and notes.
  - Support semantic search using pgvector embeddings.
- The architect should:
  - Define what content is embedded (e.g., transcript segments, summaries, notes).
  - Define the data model for embeddings (including vector type and indexing).
  - Describe how search queries are processed:
    - Keyword search via SQL
    - Semantic search via vector similarity
  - Describe how search results are ranked and presented.

### 3.9 Export to Markdown and PDF

- The system must:
  - Allow the user to export a meeting to Markdown.
  - Allow the user to export a meeting to PDF.
  - Include in the export:
    - Meeting metadata
    - Summary
    - Decisions
    - Action items
    - Transcript with speakers
    - Notes
- The architect should:
  - Describe the structure and sections of the Markdown export.
  - Describe the structure and sections of the PDF export.
  - Describe how HTML rendering and PDF generation are handled (e.g., HTML templates plus a PDF engine).
  - Describe how exports are triggered and delivered (e.g., direct download, background job for large meetings).

---

## 4. Non‑Functional Requirements

The architect must explicitly address:

- Platform: Linux (EndeavourOS, Arch‑based).
- Local processing: Audio, transcription, and LLM inference should be local by default.
- Performance: Efficient handling of long meetings and large transcripts.
- Reliability: Handling of failures in audio capture, transcription, LLM calls, and calendar sync.
- Observability: Logging, metrics, and basic monitoring strategy.
- Security:
  - Safe storage of OAuth tokens for calendars.
  - Protection of meeting data.
  - Design for future authentication and multi‑user support.
- Containerization:
  - Clear separation of services into containers (or at least into logical components that can be containerized).
  - Networking and configuration between services.

---

## 5. System Architecture and Components

You must design and describe, in detail, the following components and how they interact:

1. Web API and backend application (e.g., FastAPI or similar).
2. Audio capture service:
   - How it is invoked
   - How it interacts with PipeWire
   - How it reports status and errors
3. Transcription service:
   - Job queue or background worker model
   - Interaction with the transcription engine
4. Summarization and LLM service:
   - How it receives inputs (transcript, notes)
   - How it calls the local LLM
   - How it stores outputs and embeddings
5. Calendar integration service:
   - OAuth handling
   - Event sync
   - Auto‑record scheduler
6. Database (Postgres + pgvector):
   - Tables
   - Relationships
   - Indexes
7. Frontend web application:
   - Pages
   - Components
   - Interaction patterns
8. Export subsystem:
   - Markdown generation
   - HTML rendering
   - PDF generation

For each component, you must specify:

- Responsibilities
- Inputs and outputs
- Interfaces (e.g., API endpoints, message formats, DB interactions)
- Error handling and retry strategies
- Configuration and environment variables

---

## 6. Database Schema Requirements

You must propose a detailed relational schema in natural language (no SQL), including:

- Tables, with:
  - Names
  - Columns
  - Data types (described conceptually)
  - Constraints (e.g., primary keys, foreign keys, uniqueness)
- Relationships between tables
- Indexing strategy (e.g., which columns to index for performance)
- pgvector usage:
  - Which tables store embeddings
  - What each embedding represents
  - How similarity search is performed conceptually

At minimum, include tables for:

- Users (even if initially single‑user)
- Meetings
- Calendar accounts
- Calendar events
- Audio files or audio metadata
- Transcript segments
- Speakers
- Notes
- Summaries
- Decisions
- Action items
- Embeddings

---

## 7. API Design Requirements

You must define a clear API surface in natural language (no code), including:

- Endpoint names and paths
- HTTP methods
- Purpose of each endpoint
- Expected inputs (parameters, request bodies)
- Expected outputs (response structures)
- Error conditions and typical responses

At minimum, cover endpoints for:

- Managing meetings (create, list, get details, start/stop recording).
- Managing notes (create, list per meeting).
- Triggering or retrieving transcription and summaries.
- Managing calendar integrations (connect, disconnect, list events, toggle auto‑record).
- Search (keyword and semantic).
- Export (Markdown and PDF).

---

## 8. Background Jobs and Scheduling

You must design a background processing model, including:

- Types of jobs:
  - Transcription
  - Summarization
  - Embedding generation
  - Calendar sync
  - Auto‑record scheduling
- How jobs are enqueued and processed.
- How failures are handled and retried.
- How job status is tracked and surfaced to the user (e.g., “Transcription in progress”, “Summary ready”).

---

## 9. Frontend Architecture and UX

You must describe the frontend in enough detail that a coding agent can implement it without ambiguity, including:

- Overall navigation structure:
  - Dashboard
  - Meeting detail
  - Live meeting
  - Settings (including calendar integration)
  - Search
- Layout and key elements on each page.
- How the live meeting page behaves:
  - How recording status is shown.
  - How notes are entered and displayed.
  - How the user knows when transcription and summary are ready after the meeting.
- How speaker labels and renaming are presented.
- How search results are displayed and linked to meetings.

---

## 10. Implementation Task Breakdown

Finally, you must produce a **detailed, structured task list** for a coding agent. This should be organized by subsystem and in a logical order of implementation.

For each major subsystem (backend, audio capture, transcription, LLM integration, calendar integration, database, frontend, export, search), provide:

- A list of concrete implementation tasks.
- Dependencies between tasks (what must be done before what).
- Milestones (e.g., “MVP without calendar integration”, “Add calendar auto‑record”, “Add semantic search”, etc.).

The goal is that a coding agent can take your plan and implement the system step by step without needing to make major architectural decisions.

---

## 11. Style and Output Requirements

- Do not write any code or pseudocode.
- Use clear headings and subheadings.
- Use structured lists where appropriate.
- Be explicit and concrete; avoid vague statements.
- Assume the implementer is competent but relies on you for all architectural decisions.

---

End of prompt.