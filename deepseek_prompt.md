# **SYSTEM ARCHITECT PROMPT: LOCAL AI MEETING ASSISTANT**

## **ROLE & CONTEXT**
You are an expert system architect with deep expertise in: **Linux audio systems (PulseAudio/PipeWire), local AI deployment (Whisper, Ollama, diarization), full-stack web development (Django/FastAPI + PostgreSQL), and privacy-first application design.**

Your task is to create a **comprehensive, phase-by-phase implementation blueprint** for a technically complex application. This blueprint will be executed by a coding agent who needs extreme specificity. You must **think step-by-step** about architecture before delivering the final plan.

## **CORE MISSION**
Design a **self-hosted, local-first web application** that transforms how technical Linux users handle meetings. The system must:
1.  **Capture meetings passively** (no bot participation) by recording **both system output AND microphone simultaneously**, even with headphones.
2.  **Process everything locally** using AI (transcription → diarization → summarization) via tools like Whisper and Ollama.
3.  **Provide a professional dashboard** for note-taking during meetings (with auto-timestamps), reviewing past meetings, and semantic search.
4.  **Automate via calendar integration** and provide robust export capabilities.

**Primary Constraint:** Privacy is non-negotiable. All processing must default to local execution. Cloud APIs are forbidden unless user explicitly configures alternatives.

---

## **TECHNICAL SPECIFICATIONS FOR ARCHITECTURAL PLANNING**

### **1. CRITICAL FOUNDATION: THE AUDIO CAPTURE PROBLEM**
This is the **most technically challenging component**. You must architect a solution for:
- **Simultaneous capture** of desktop audio (application/browser output) and microphone input.
- **Headphone compatibility**: The solution must work when the user's audio output is routed to headphones (not speakers).
- **Linux audio stack specifics**: Design for **PulseAudio** (common) with a path forward for **PipeWire** (modern).
- **Synchronization**: Methods to align the two audio streams with minimal latency/drift.

**Consider these approaches in your thinking:**
- **PulseAudio**: Creating a "combined sink" or using `module-combine-sink` + `module-loopback` to monitor.
- **PipeWire**: Using `pw-loopback` to create audio links.
- **Fallback strategy**: What if direct system capture fails? Could we capture from a "virtual microphone" that applications send audio to?

### **2. LOCAL AI PROCESSING PIPELINE ARCHITECTURE**
Design a **modular, queued pipeline** that transforms audio → useful insights:
```
Audio File → [Transcription (Whisper)] → [Diarization (PyAnnote)] → [Merge & Timestamp] → [LLM Processing (Ollama)] → [Database Storage]
```
**Key architectural decisions needed:**
1.  **Model Selection & Management**:
    - Which **Whisper variant** (faster-whisper, whisper.cpp) balances speed/accuracy on CPU?
    - How to handle **diarization model download** (PyAnnote requires Hugging Face token).
    - **LLM coordination**: How will the system interact with Ollama? Which model (e.g., Mistral, Llama 3) for summarization?

2.  **Resource & Queue Management**:
    - Processing a 60-minute meeting requires significant CPU/RAM. How to prevent UI blocking?
    - Design a **job queue system** (Celery + Redis vs. RQ vs. Dramatiq) with priority levels.
    - How to handle **partial failures** (e.g., diarization fails but transcription succeeds)?

### **3. DATA MODEL & SEARCH INTEGRATION**
PostgreSQL + pgvector must store:
- **Hierarchical meeting data** (Meeting → Transcript segments → Notes → Summary)
- **Vector embeddings** for semantic search across all historical content

**Design considerations:**
- **Embedding generation strategy**: When are embeddings created? Which model (sentence-transformers)? Batch or real-time?
- **Search architecture**: How does pgvector integrate with traditional text search (full-text vs. semantic)?
- **Note synchronization**: How are timestamped notes stored/retrieved/linked to transcript segments?

### **4. CALENDAR INTEGRATION DESIGN**
Two primary integration paths require different architectures:

| **Method** | **Authentication** | **Polling Mechanism** | **Challenges to Solve** |
|------------|-------------------|----------------------|-------------------------|
| **Google Calendar API** | OAuth 2.0 with refresh tokens | Calendar watch/channel API vs. periodic polling | Token management, meeting link detection in events |
| **CalDAV (Generic)** | Basic auth/CalDAV-specific | iCalendar (.ics) download and parsing | Recurring event handling, timezone normalization |

**Architectural decisions:**
- **Polling service design**: Should it run as a separate process? How to avoid missing meetings?
- **Meeting detection logic**: How to identify which calendar events are "video meetings"?
- **User control interface**: How to enable/disable auto-recording per calendar or per event?

### **5. WEB APPLICATION ARCHITECTURE**
**Frontend/Backend separation strategy:**
- **Option A**: Django with server-rendered templates + HTMX for interactivity
- **Option B**: FastAPI backend + lightweight JavaScript frontend (Alpine.js)
- **Real-time requirements**: Note-taking during meetings needs near-instant save. WebSockets vs. frequent AJAX?

**UI/UX critical flows to design:**
1.  **Recording control interface** (start/stop, status, audio level monitoring)
2.  **Live meeting view** (transcript updating in real-time, note-taking panel with timestamp sync)
3.  **Playback experience** (transcript scrolling synchronized with audio playback)

### **6. EXPORT & OUTPUT GENERATION**
**Multi-format export system:**
- **Markdown generation**: Template engine (Jinja2) structuring transcript, notes, summary
- **PDF creation**: Library selection (WeasyPrint vs. ReportLab) balancing simplicity vs. styling control
- **Storage strategy**: Generate-on-demand vs. cache generated files

---

## **YOUR THINKING & OUTPUT FRAMEWORK**

### **PHASE 1: INITIAL ANALYSIS (THINK THROUGH THESE)**
Before writing the implementation plan, analyze:

1.  **Dependency Graph Analysis**:
    - Map all required system dependencies (Python libs, system packages, audio stack components)
    - Identify which are available via pip vs. require system packages vs. need manual installation
    - Consider dependency conflicts (e.g., PyTorch versions for Whisper vs. diarization)

2.  **Failure Mode Analysis**:
    - What happens if PulseAudio isn't running?
    - What if Ollama isn't installed or the model isn't downloaded?
    - How does the system degrade gracefully when resources are limited?

3.  **Data Flow Optimization**:
    - Should audio be processed in chunks or as a whole file?
    - When should embeddings be generated (immediately after processing vs. on-demand)?
    - How to cache LLM responses for similar meetings?

### **PHASE 2: IMPLEMENTATION BLUEPUILD STRUCTURE**
Your final output must be organized as:

**PART 1: SYSTEM ARCHITECTURE OVERVIEW**
- Technology stack justification table
- System component interaction diagram (conceptual)
- Data flow specification

**PART 2: PHASED IMPLEMENTATION BLUEPRINT**
Break into **7 phases** with **specific, actionable tasks**. Each task must include:

```
### [PHASE X.Y] Task Name
**OBJECTIVE**: One sentence describing what this task accomplishes
**PREREQUISITES**: Which previous tasks must be complete
**SPECIFICATIONS**:
- Library/Technology: [Exact library and version to use]
- Configuration: [Key configuration parameters to set]
- Integration Points: [How this connects to other components]
**IMPLEMENTATION STEPS**:
1. [Step 1 - specific action]
2. [Step 2 - specific action]
3. [Step 3 - specific action]
**VALIDATION CRITERIA**: How to test this component works
**OUTPUT ARTIFACT**: What file/component is produced
```

**Required Phases:**
1.  **Environment & Foundation** - Project setup, database, core dependencies
2.  **Audio Capture Engine** - The critical audio recording subsystem
3.  **AI Pipeline Modules** - Transcription, diarization, LLM integration as independent components
4.  **Core Data System** - PostgreSQL models, pgvector setup, embedding generation
5.  **Web Application Framework** - Backend API, frontend interface, real-time features
6.  **Integration Features** - Calendar, export, search functionality
7.  **Deployment & Packaging** - Systemd services, Arch Linux packaging, configuration management

**PART 3: DEPENDENCY & RISK MATRIX**
- Table of external dependencies with installation methods
- Risk assessment for each major component
- Mitigation strategies for high-risk components

**PART 4: TESTING & VALIDATION PLAN**
- Unit test strategy for each module
- Integration test scenarios
- Performance benchmarks for AI components

---

## **SPECIFIC INSTRUCTIONS FOR FINAL OUTPUT**

1.  **Be prescriptive, not descriptive**: The coding agent needs exact commands and libraries. Instead of "set up a database," specify "Install PostgreSQL 15+ via `pacman -S postgresql`, initialize with `sudo -iu postgres initdb -D /var/lib/postgres/data`, enable with `systemctl enable --now postgresql`."

2.  **Address Linux-specific complexities**:
    - Include commands for Arch-based systems (endeavourOS)
    - Consider audio stack peculiarities
    - Handle permission issues (PulseAudio access, service management)

3.  **Design for extensibility**:
    - How could someone add Zoom/Teams transcript import later?
    - How could cloud processing be added as an optional alternative?
    - How to swap Whisper for a different ASR engine?

4.  **Include concrete examples**:
    - Example Celery task signature for audio processing
    - Example database schema (table names, columns, relationships)
    - Example Ollama API prompt for action item extraction

5.  **Prioritize the hard problems first**:
    - Audio capture is the highest risk. Dedicate significant detail to this.
    - Diarization accuracy tuning is complex. Provide configuration guidance.

**Remember**: You are creating a blueprint for another AI to execute. Ambiguity will cause failure. Specificity enables success. Think through the entire system, then provide the exact step-by-step plan to build it.

---

**BEGIN YOUR ANALYSIS AND CREATE THE IMPLEMENTATION BLUEPRINT**