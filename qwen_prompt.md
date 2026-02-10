# Claude Opus 4.6 Implementation Plan Request
## AI Meeting Assistant - Comprehensive System Architecture & Implementation Strategy

---

## 🎯 PROJECT CONTEXT & OBJECTIVE

You are tasked with developing a **comprehensive implementation plan** for a sophisticated Linux-based AI meeting assistant web application. This is not a simple CRUD application—it requires deep integration with Linux audio systems, real-time AI processing, calendar synchronization, and advanced database architecture with vector search capabilities.

The final deliverable must be **execution-ready** for a coding specialist who will implement the system based solely on your plan. Every architectural decision, technology choice, and implementation detail must be justified and clearly specified.

---

## 📋 PROJECT BACKGROUND & MOTIVATION

### The Problem Space
The user currently uses EndeavourOS (Arch-based Linux) and needs a meeting transcription/summarization tool similar to Granola AI, but Granola doesn't support Linux. The solution must:
- **Passively record** system audio (not join as a bot)
- **Work with headphones** connected
- Provide **speaker diarization** (identify different speakers)
- Allow **real-time note-taking** with automatic timestamping
- **Integrate with calendars** for auto-recording
- **Export to Markdown and PDF** with professional formatting
- Be **self-hosted** with no cloud dependencies for privacy

### Why This Architecture?
The chosen stack (PostgreSQL + pgvector, WhisperX, FastAPI, React) represents the optimal balance of:
- **Performance**: GPU-accelerated transcription with efficient vector search
- **Privacy**: All processing happens locally on user's machine
- **Scalability**: Can handle thousands of meetings with proper indexing
- **Maintainability**: Well-documented, mature open-source technologies
- **Linux Compatibility**: All components work natively on Arch-based systems

---

## 🏗️ SYSTEM ARCHITECTURE REQUIREMENTS

### Core Technical Constraints
- **OS**: EndeavourOS (Arch Linux) - must work with both PulseAudio and PipeWire
- **Audio Capture**: System-level audio capture without virtual audio cables
- **Processing**: Local-first, no external API dependencies for core functionality
- **Database**: PostgreSQL 15+ with pgvector extension for semantic search
- **Language**: Python 3.10+ for backend, TypeScript for frontend
- **Deployment**: Docker-compose for easy setup, but also support native installation

### Functional Requirements Breakdown

#### 1. Audio Subsystem (Critical Path)
**Requirements:**
- Capture system audio from any application (Zoom, Teams, Google Meet, etc.)
- Support simultaneous headphone output and recording
- Handle audio format conversion (44.1kHz → 16kHz for Whisper)
- Provide real-time audio level monitoring
- Gracefully handle audio device changes during recording
- Support both mono and stereo input with configurable downmixing

**Key Questions to Address:**
- Should we use PulseAudio monitor sinks or PipeWire streams?
- How to handle different sample rates across applications?
- What's the optimal buffer size for real-time processing vs. latency?
- How to detect and recover from audio capture failures?

#### 2. Transcription & Speaker Diarization Pipeline
**Requirements:**
- Real-time transcription with < 2 second latency
- Speaker diarization with > 90% accuracy
- Word-level timestamp alignment
- Support for 10+ languages with auto-detection
- Configurable model sizes (tiny → large) for speed/accuracy tradeoff
- GPU acceleration when available, CPU fallback when not
- Batch processing capability for long recordings

**Technology Stack Analysis:**
- **WhisperX** vs. **faster-whisper** vs. **whisper.cpp**
- **pyannote.audio** vs. **NVIDIA NeMo** for diarization
- **CTranslate2** for inference optimization
- **ONNX Runtime** vs. **PyTorch** deployment

**Performance Considerations:**
- Memory usage for different model sizes
- GPU VRAM requirements
- CPU-only performance benchmarks
- Streaming vs. batch processing tradeoffs

#### 3. Calendar Integration System
**Requirements:**
- Support Google Calendar and Microsoft Outlook/Office 365
- OAuth2 authentication with secure token storage
- Webhook-based event notifications (preferred) or polling fallback
- Auto-recording trigger 30 seconds before meeting start
- Auto-stop recording at meeting end
- Manual override capability for individual meetings
- Calendar event metadata extraction (title, participants, description)

**Implementation Approaches:**
- **Direct API Integration**: Full control, more implementation work
- **Third-party Service**: Faster implementation, potential cost/dependency
- **Hybrid Approach**: Core functionality direct, advanced features via service

**Security Considerations:**
- OAuth token encryption at rest
- Refresh token handling
- Scope minimization (calendar read-only)
- Token expiration and renewal strategies

#### 4. Note-Taking & Timestamp Integration
**Requirements:**
- Real-time note entry during recording
- Automatic timestamp capture (relative to meeting start)
- Manual timestamp adjustment post-meeting
- Rich text formatting (bold, italic, lists, code blocks)
- Note categories/tags (action item, question, decision, etc.)
- Inline display with transcript
- Search across notes with semantic capabilities

**UX Considerations:**
- Keyboard shortcuts for quick note entry
- Visual timestamp indicators in transcript
- Note highlighting and filtering
- Undo/redo functionality
- Note export/import capabilities

#### 5. Vector Search & Semantic Capabilities
**Requirements:**
- pgvector integration for transcript embeddings
- Semantic search across all meetings
- Hybrid search (keyword + vector)
- Relevance scoring and ranking
- Query expansion and suggestion
- Search history and saved searches

**Embedding Strategy:**
- **SentenceTransformers** vs. **OpenAI embeddings** (local vs. API)
- Chunking strategy for long transcripts
- Embedding dimension selection (384, 768, 1536)
- Index type selection (IVFFlat, HNSW)
- Update strategy for new meetings

#### 6. Export System
**Requirements:**
- Markdown export with customizable templates
- PDF export with professional styling
- JSON export for programmatic access
- Batch export capability
- Template system for custom formatting
- Export history tracking

**Technical Implementation:**
- **Markdown**: Jinja2 templates with data injection
- **PDF**: WeasyPrint (HTML→PDF) vs. ReportLab (direct PDF generation)
- **Styling**: CSS for PDF, custom themes support
- **Assets**: Font embedding, image handling

---

## 📊 DATABASE ARCHITECTURE SPECIFICATION

### Schema Design Requirements

#### Core Tables
1. **users** - Authentication and preferences
2. **meetings** - Meeting metadata and status
3. **transcripts** - Transcribed text with timestamps
4. **transcript_segments** - Word-level segments with speaker labels
5. **notes** - User notes with timestamps and categories
6. **action_items** - Extracted action items with assignments
7. **calendar_connections** - OAuth credentials and sync state
8. **calendar_events** - Cached calendar events for auto-recording
9. **exports** - Export history and file locations
10. **search_embeddings** - Vector embeddings for semantic search

#### Relationships & Constraints
- Foreign key relationships between all related entities
- Cascade delete strategies for data integrity
- Unique constraints for business rules
- Check constraints for data validation

#### Indexing Strategy
- **B-tree indexes** for exact match queries (user_id, meeting_id, timestamps)
- **GIN indexes** for full-text search on transcripts and notes
- **pgvector indexes** (IVFFlat or HNSW) for semantic search
- **Partial indexes** for filtered queries (active meetings, completed exports)
- **Composite indexes** for common query patterns

#### Migration Strategy
- Initial schema creation
- Data migration from existing systems (if any)
- Version control for schema changes
- Rollback procedures for failed migrations

---

## 🔌 API & COMMUNICATION LAYER

### REST API Specification
**Base URL**: `/api/v1`

#### Meeting Endpoints
- `POST /meetings` - Create new meeting (manual start)
- `GET /meetings` - List meetings with filtering/pagination
- `GET /meetings/{id}` - Get meeting details
- `PUT /meetings/{id}` - Update meeting metadata
- `DELETE /meetings/{id}` - Delete meeting and associated data

#### Recording Endpoints
- `POST /recordings/start` - Start recording
- `POST /recordings/stop` - Stop recording
- `GET /recordings/status` - Get current recording status
- `GET /recordings/{id}/audio` - Download audio file

#### Transcript Endpoints
- `GET /meetings/{id}/transcript` - Get full transcript
- `GET /meetings/{id}/transcript/segments` - Get word-level segments
- `POST /meetings/{id}/transcript/regenerate` - Re-transcribe meeting

#### Note Endpoints
- `POST /meetings/{id}/notes` - Create note
- `GET /meetings/{id}/notes` - Get all notes
- `PUT /meetings/{id}/notes/{note_id}` - Update note
- `DELETE /meetings/{id}/notes/{note_id}` - Delete note

#### Search Endpoints
- `POST /search` - Semantic search across meetings
- `GET /search/history` - Get search history
- `POST /search/suggest` - Get query suggestions

#### Export Endpoints
- `POST /meetings/{id}/export/markdown` - Export to Markdown
- `POST /meetings/{id}/export/pdf` - Export to PDF
- `POST /meetings/{id}/export/json` - Export to JSON
- `GET /exports` - List all exports

#### Calendar Endpoints
- `POST /calendar/connect/google` - Connect Google Calendar
- `POST /calendar/connect/outlook` - Connect Outlook Calendar
- `GET /calendar/status` - Get calendar sync status
- `POST /calendar/sync` - Trigger manual sync

### WebSocket Communication
**Endpoint**: `/ws/meetings/{id}`

#### Real-time Events
- `recording_started` - Recording has begun
- `recording_stopped` - Recording has ended
- `transcript_update` - New transcript segment available
- `note_added` - New note has been added
- `audio_level_update` - Audio levels for visualization
- `processing_progress` - Transcription/processing progress

#### Client Messages
- `add_note` - Add timestamped note
- `update_meeting_title` - Update meeting title during recording
- `request_transcript` - Request current transcript state

---

## 🎨 FRONTEND ARCHITECTURE

### Component Hierarchy

#### Layout Components
- **AppShell** - Main application layout
- **Sidebar** - Navigation and filters
- **Header** - Search bar and user controls
- **Footer** - Status indicators and quick actions

#### Page Components
- **DashboardPage** - Meeting list and statistics
- **RecordingPage** - Recording control panel
- **MeetingDetailPage** - Transcript and notes view
- **SettingsPage** - Configuration and preferences
- **CalendarPage** - Calendar integration settings

#### Feature Components
- **MeetingList** - Grid/list view of meetings
- **TranscriptViewer** - Scrollable transcript with speaker labels
- **NoteEditor** - Rich text editor for notes
- **AudioVisualizer** - Real-time audio level display
- **SearchBar** - Global search with suggestions
- **ExportDialog** - Export configuration and preview

### State Management Strategy
- **Global State**: User preferences, authentication, app settings
- **Meeting State**: Current meeting data, recording status
- **UI State**: Open dialogs, active filters, selected items
- **Real-time State**: Live transcript updates, audio levels

### Routing Strategy
- Client-side routing with React Router or Vue Router
- Route guards for authentication
- Deep linking to specific meetings and timestamps
- Browser history integration

---

## 🧪 TESTING STRATEGY

### Unit Testing
- **Backend**: pytest for all service layers
- **Frontend**: Jest/Vitest for components and utilities
- **Coverage Target**: 80%+ for critical paths

### Integration Testing
- **API Integration**: Test all endpoints with realistic data
- **Database Integration**: Test queries, transactions, and constraints
- **Audio Integration**: Test audio capture and processing pipeline

### End-to-End Testing
- **User Flows**: Recording → transcription → note-taking → export
- **Calendar Integration**: OAuth flow and auto-recording
- **Search Functionality**: Keyword and semantic search

### Performance Testing
- **Transcription Speed**: Benchmark different model sizes
- **Search Performance**: Test with 1000+ meetings
- **Memory Usage**: Monitor during long recordings
- **Database Query Performance**: EXPLAIN ANALYZE for critical queries

### Security Testing
- **Authentication**: Test token handling and expiration
- **Authorization**: Verify access controls
- **Input Validation**: Test for SQL injection, XSS
- **Data Encryption**: Verify sensitive data protection

---

## 📦 DEPLOYMENT & OPERATIONS

### Docker Configuration
- **Backend Service**: FastAPI application with dependencies
- **Frontend Service**: React/Vue build with Nginx
- **Database Service**: PostgreSQL with pgvector
- **Worker Service**: Celery workers for background tasks
- **Reverse Proxy**: Traefik or Nginx for routing

### System Requirements
- **Minimum**: 4 CPU cores, 8GB RAM, 50GB storage
- **Recommended**: 8 CPU cores, 16GB RAM, 100GB storage + GPU
- **GPU**: NVIDIA GPU with 4GB+ VRAM for accelerated transcription

### Installation Process
1. Clone repository
2. Configure environment variables
3. Run docker-compose up
4. Initialize database
5. Create admin user
6. Configure audio settings

### Backup & Recovery
- **Database Backups**: Automated daily dumps
- **File Backups**: Audio files and exports
- **Configuration Backups**: Environment variables and settings
- **Restore Procedures**: Step-by-step recovery guide

### Monitoring & Logging
- **Application Logs**: Structured JSON logging
- **Error Tracking**: Sentry or similar service
- **Performance Metrics**: Response times, processing speeds
- **Resource Monitoring**: CPU, memory, disk usage

---

## 📚 DOCUMENTATION REQUIREMENTS

### User Documentation
- **Getting Started Guide**: Installation and first meeting
- **User Manual**: All features and workflows
- **FAQ**: Common questions and troubleshooting
- **Keyboard Shortcuts**: Quick reference guide
- **Video Tutorials**: Screen recordings of key workflows

### Developer Documentation
- **Architecture Overview**: System design and decisions
- **API Documentation**: OpenAPI/Swagger specification
- **Database Schema**: ER diagrams and table descriptions
- **Development Setup**: Local development environment
- **Contribution Guide**: How to contribute to the project

### Technical Documentation
- **Deployment Guide**: Production deployment steps
- **Security Guide**: Security best practices
- **Performance Guide**: Optimization tips
- **Troubleshooting Guide**: Common issues and solutions

---

## 🎯 SUCCESS CRITERIA & DELIVERABLES

### Phase 1: MVP (Weeks 1-6)
**Deliverables:**
- Basic audio capture and recording
- Post-meeting transcription with speaker diarization
- Simple web interface for meeting list and details
- Manual note-taking with timestamping
- Markdown export functionality

**Success Metrics:**
- Can record and transcribe a 1-hour meeting
- Speaker diarization accuracy > 85%
- Transcription latency < 5 minutes for 1-hour meeting
- Basic UI is functional and usable

### Phase 2: Core Features (Weeks 7-10)
**Deliverables:**
- Real-time transcription during recording
- Calendar integration with auto-recording
- Enhanced note-taking with rich text
- PDF export with professional styling
- Basic search functionality

**Success Metrics:**
- Real-time transcription latency < 2 seconds
- Calendar sync reliability > 99%
- PDF exports match design specifications
- Search returns relevant results

### Phase 3: Advanced Features (Weeks 11-14)
**Deliverables:**
- Semantic search with pgvector
- AI-powered summarization and action item extraction
- Advanced filtering and sorting
- Template system for exports
- Performance optimizations

**Success Metrics:**
- Semantic search relevance score > 0.8
- Summarization captures key points accurately
- System handles 100+ meetings efficiently
- Response times < 500ms for most operations

### Phase 4: Polish & Production (Weeks 15-16)
**Deliverables:**
- Comprehensive testing suite
- Production deployment documentation
- User documentation and tutorials
- Performance tuning and optimization
- Security audit and hardening

**Success Metrics:**
- Test coverage > 80%
- Zero critical bugs in production
- Documentation is complete and accurate
- System is stable under load

---

## 🤔 CRITICAL DECISION POINTS & TRADEOFFS

### 1. Audio Capture Strategy
**Options:**
- **PulseAudio Monitor Sinks**: Mature, widely supported, but being phased out
- **PipeWire Streams**: Modern, better performance, but newer ecosystem
- **OBS Studio Integration**: Robust but adds dependency
- **ALSA Loopback**: Low-level, maximum control but complex

**Analysis Required:**
- Compatibility with EndeavourOS default audio setup
- Performance impact on system audio
- Ease of implementation and maintenance
- Error handling and recovery capabilities

### 2. Transcription Engine Selection
**Options:**
- **WhisperX**: Best accuracy, good diarization integration, moderate speed
- **faster-whisper**: Faster inference, slightly lower accuracy
- **whisper.cpp**: CPU-optimized, no Python dependency, lower accuracy
- **NVIDIA NeMo**: Enterprise-grade, requires NVIDIA GPU

**Analysis Required:**
- Accuracy vs. speed tradeoffs for different use cases
- GPU vs. CPU performance benchmarks
- Memory usage and system requirements
- Ease of integration with diarization pipeline

### 3. Frontend Framework Choice
**Options:**
- **React + TypeScript**: Large ecosystem, excellent tooling
- **Vue 3 + TypeScript**: Simpler learning curve, great performance
- **Svelte**: Minimal boilerplate, excellent performance
- **SolidJS**: React-like API with better performance

**Analysis Required:**
- Developer familiarity and team skills
- Ecosystem maturity and component libraries
- Performance characteristics for real-time updates
- TypeScript support and type safety

### 4. Vector Search Strategy
**Options:**
- **pgvector (IVFFlat)**: Simple, good for < 100k vectors
- **pgvector (HNSW)**: Better performance, more complex setup
- **Weaviate**: Dedicated vector database, more features
- **Qdrant**: High-performance, but external dependency

**Analysis Required:**
- Expected scale (number of meetings and transcripts)
- Query performance requirements
- Operational complexity vs. performance
- Integration complexity with existing PostgreSQL

### 5. PDF Generation Approach
**Options:**
- **WeasyPrint**: HTML→PDF, excellent CSS support
- **ReportLab**: Direct PDF generation, more control
- **PyMuPDF**: Fast, good for simple documents
- **LaTeX**: Professional quality, steep learning curve

**Analysis Required:**
- Output quality requirements
- Template flexibility needs
- Performance for batch exports
- Maintenance complexity

---

## 📝 EXPECTED OUTPUT FORMAT

Your implementation plan should be structured as follows:

### 1. Executive Summary
- High-level overview of the proposed architecture
- Key technology choices and justifications
- Estimated timeline and resource requirements
- Risk assessment and mitigation strategies

### 2. System Architecture Diagram
- Component diagram showing all services and interactions
- Data flow diagram from audio capture to export
- Deployment architecture (Docker containers, services)
- Technology stack visualization

### 3. Technology Stack Deep Dive
For each major component:
- **Technology Choice**: Specific library/tool with version
- **Justification**: Why this choice over alternatives
- **Integration Approach**: How it integrates with other components
- **Configuration Requirements**: Setup and tuning parameters
- **Performance Characteristics**: Benchmarks and expectations
- **Potential Issues**: Known limitations and workarounds

### 4. Database Schema Specification
- Complete table definitions with all columns
- Data types, constraints, and default values
- Index specifications with rationale
- Foreign key relationships
- Migration scripts for initial setup
- Sample data for testing

### 5. API Specification
- Complete endpoint list with HTTP methods
- Request/response schemas (JSON examples)
- Authentication and authorization requirements
- Error handling patterns
- Rate limiting and throttling strategies
- WebSocket message formats

### 6. Implementation Phases
For each phase:
- **Phase Goals**: What will be delivered
- **Task Breakdown**: Specific development tasks
- **Dependencies**: What must be completed first
- **Timeline**: Estimated duration for each task
- **Success Criteria**: How to verify completion
- **Testing Requirements**: What needs to be tested

### 7. Configuration Management
- Environment variable specifications
- Configuration file structure and format
- Default values and override mechanisms
- Security considerations for sensitive data
- Multi-environment support (dev, staging, prod)

### 8. Testing Strategy
- Test pyramid breakdown (unit, integration, e2e)
- Test coverage targets
- Testing tools and frameworks
- CI/CD integration points
- Performance testing approach
- Security testing checklist

### 9. Deployment Architecture
- Docker container specifications
- Docker-compose configuration
- System requirements (hardware, software)
- Installation instructions (step-by-step)
- Backup and recovery procedures
- Monitoring and logging setup

### 10. Risk Assessment & Mitigation
- Technical risks (performance, scalability, compatibility)
- Operational risks (deployment, maintenance, upgrades)
- Security risks (data protection, authentication)
- Mitigation strategies for each identified risk
- Contingency plans for critical failures

### 11. Documentation Plan
- Documentation structure and organization
- Tools and formats for each documentation type
- Review and maintenance process
- Localization strategy (if applicable)

### 12. Future Enhancements Roadmap
- Phase 5+ features and capabilities
- Potential integrations (Slack, Notion, etc.)
- Advanced AI features (sentiment analysis, topic modeling)
- Mobile app considerations
- Multi-user collaboration features

---

## 🎓 ADDITIONAL CONSIDERATIONS

### Linux-Specific Considerations
- **Audio System Detection**: Auto-detect PulseAudio vs. PipeWire
- **Package Dependencies**: System packages required for audio capture
- **Permissions**: Required user permissions for audio access
- **Desktop Integration**: System tray, notifications, file associations

### Performance Optimization Opportunities
- **GPU Acceleration**: CUDA vs. ROCm support
- **Model Quantization**: Reduce model size for faster inference
- **Caching Strategy**: Cache frequent queries and results
- **Background Processing**: Offload heavy tasks to workers
- **Database Optimization**: Connection pooling, query optimization

### Accessibility & Internationalization
- **WCAG 2.1 AA Compliance**: Accessibility standards
- **Keyboard Navigation**: Full keyboard support
- **Screen Reader Support**: ARIA labels and semantic HTML
- **i18n Support**: Multi-language interface (future)
- **RTL Support**: Right-to-left language support (future)

### Security Best Practices
- **Authentication**: JWT tokens with refresh mechanism
- **Authorization**: Role-based access control
- **Data Encryption**: Encrypt sensitive data at rest
- **Input Validation**: Sanitize all user inputs
- **Security Headers**: CSP, HSTS, X-Frame-Options
- **Dependency Scanning**: Regular security audits

---

## ✅ FINAL DELIVERABLE REQUIREMENTS

Your implementation plan must be **comprehensive enough** that a coding specialist can:

1. **Understand the complete system architecture** without asking clarifying questions
2. **Implement each component** following your specifications exactly
3. **Make informed decisions** about edge cases based on your guidance
4. **Test the system** according to your testing strategy
5. **Deploy the system** using your deployment instructions
6. **Maintain and extend** the system based on your documentation plan

The plan should demonstrate **deep technical expertise**, **practical implementation knowledge**, and **strategic thinking** about tradeoffs and future scalability.

**Remember**: This is not just a high-level overview—it must be a **detailed, actionable blueprint** that transforms the requirements into a concrete implementation strategy.

---

**Begin your comprehensive implementation plan now.**