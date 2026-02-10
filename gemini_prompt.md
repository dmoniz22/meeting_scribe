# ARCHITECTURAL SPECIFICATION: Local Bot-less Meeting Intelligence System (Linux)

## Role & Goal

You are a Senior Systems Architect specializing in Linux audio engineering and AI-integrated web applications. Your task is to develop a production-ready **Implementation Plan** for a "Bot-less" meeting transcriber on EndeavourOS.

## Core Technical Differentiator

Unlike cloud-based competitors, this system **must not** join calls as a bot. It must capture audio via a local **PipeWire loopback**, merge system and microphone streams, and process everything locally or via private API, ensuring total privacy and headphone compatibility.

## System Constraints

* **Host OS:** EndeavourOS (Kernel 6.x+, PipeWire 1.x+).
* **Backend:** Python 3.12 (FastAPI) + PostgreSQL 17 + `pgvector`.
* **Audio Stack:** PipeWire, `wireplumber`, and `ffmpeg` for low-latency capture.
* **AI Stack:** WhisperX (for diarization), Ollama (local Llama 3/Mistral for summarization), and `all-MiniLM-L6-v2` for embeddings.
* **Frontend:** Next.js 15 (App Router) + Tailwind CSS + Lucide Icons.

## Detailed Requirements for Planning

### 1. Audio Capture & Daemonization

* Design a PipeWire virtual sink strategy using `pw-loopback` or `wireplumber` scripts to merge `Monitor of [Headphones]` and `Default Microphone` into a single virtual source.
* Detail a background recording service (Python/Shell) that can be triggered via a REST API. It must support `.wav` chunking to allow for "near real-time" processing.

### 2. The "Timestamp-Sync" Architecture

* Define a logic for reconciling the **Meeting Start Time** (Unix Epoch) with the **Recording Offset**.
* **Crucial Feature:** Manual notes taken in the UI must be saved with a `system_timestamp`. Architect a way to map these notes to the exact word-level timestamp provided by WhisperX.

### 3. Data Modeling & Vector Search

* Design a PostgreSQL schema optimized for RAG.
* Include a `Meetings` table, a `Transcript_Segments` table with `pgvector` columns, and a `Manual_Notes` table.
* Define a "Note Integration" view or function that interleaves user notes with transcript segments based on time-overlap.

### 4. Calendar & Automation

* Outline an OAuth2 flow for Google/Outlook calendars.
* Design a "Scheduler Service" that polls the calendar and uses `at` or `systemd-run` to schedule the recording start/stop based on meeting invite details.

### 5. Speaker Diarization & Transcription

* Use **WhisperX** as the primary engine. Explain how to manage the GPU memory handoff between Whisper (transcription), Pyannote (diarization), and the LLM (summarization) to avoid VRAM crashes on a local Linux machine.

## Requested Output Format for the Plan

Please structure your response into the following clear sections for the subsequent **Coding Agent**:

1. **Component Topology Map:** A clear breakdown of services (Frontend, API, Recording Daemon, DB).
2. **Audio Routing Logic:** Specific PipeWire/FFmpeg commands required to achieve the "Bot-less" capture.
3. **The API Spec:** Definition of endpoints for `/start-meeting`, `/post-note`, and `/generate-summary`.
4. **Step-by-Step Implementation Roadmap:**
* **Milestone 1:** PipeWire Audio Loopback & CLI Recorder.
* **Milestone 2:** Backend API & Postgres/pgvector Schema.
* **Milestone 3:** WhisperX + Diarization Pipeline integration.
* **Milestone 4:** Frontend Dashboard with real-time note-taking & Calendar Sync.
* **Milestone 5:** RAG Search & PDF/Markdown Export engine.


5. **Risk & Optimization Mitigation:** Specific advice on handling Linux audio permissions and GPU resource management.