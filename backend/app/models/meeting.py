import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    ARRAY,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    meetings = relationship(
        "Meeting", back_populates="user", cascade="all, delete-orphan"
    )
    notes = relationship("Note", back_populates="user", cascade="all, delete-orphan")
    calendar_connections = relationship(
        "CalendarConnection", back_populates="user", cascade="all, delete-orphan"
    )


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String(500), nullable=False, default="Untitled Meeting")
    status = Column(
        String(20), nullable=False, default="idle"
    )  # idle, recording, recorded, transcribing, transcribed, summarizing, completed, failed
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    audio_path = Column(String(1000), nullable=True)
    calendar_event_id = Column(
        UUID(as_uuid=True), ForeignKey("calendar_events.id"), nullable=True
    )
    tags = Column(ARRAY(Text), default=list)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="meetings")
    speakers = relationship(
        "Speaker", back_populates="meeting", cascade="all, delete-orphan"
    )
    transcript_segments = relationship(
        "TranscriptSegment", back_populates="meeting", cascade="all, delete-orphan"
    )
    notes = relationship("Note", back_populates="meeting", cascade="all, delete-orphan")
    summary = relationship(
        "Summary", back_populates="meeting", uselist=False, cascade="all, delete-orphan"
    )
    exports = relationship(
        "Export", back_populates="meeting", cascade="all, delete-orphan"
    )
    calendar_event = relationship("CalendarEvent", back_populates="meetings")

    # Indexes
    __table_args__ = (
        Index("idx_meetings_user_started", "user_id", "started_at"),
        Index("idx_meetings_status", "status"),
    )


class Speaker(Base):
    __tablename__ = "speakers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    label = Column(String(50), nullable=False)  # SPEAKER_00, SPEAKER_01, etc.
    display_name = Column(String(100), nullable=True)  # User-assigned name
    color = Column(String(7), nullable=False, default="#3B82F6")  # Hex color for UI

    # Relationships
    meeting = relationship("Meeting", back_populates="speakers")
    transcript_segments = relationship("TranscriptSegment", back_populates="speaker")

    # Indexes
    __table_args__ = (Index("idx_speakers_meeting", "meeting_id"),)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    speaker_id = Column(UUID(as_uuid=True), ForeignKey("speakers.id"), nullable=True)
    start_time = Column(Float, nullable=False)  # Offset in seconds from meeting start
    end_time = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=True)  # WhisperX confidence score
    embedding = Column(Vector(384), nullable=True)  # 384-dim vector for semantic search

    # Relationships
    meeting = relationship("Meeting", back_populates="transcript_segments")
    speaker = relationship("Speaker", back_populates="transcript_segments")

    # Indexes
    __table_args__ = (Index("idx_segments_meeting_time", "meeting_id", "start_time"),)


class Note(Base):
    __tablename__ = "notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    recording_offset = Column(Float, nullable=False)  # Seconds from meeting start
    content = Column(Text, nullable=False)
    note_type = Column(
        String(20), default="general"
    )  # general, action_item, decision, question
    embedding = Column(Vector(384), nullable=True)  # 384-dim vector for semantic search
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    meeting = relationship("Meeting", back_populates="notes")
    user = relationship("User", back_populates="notes")

    # Indexes
    __table_args__ = (
        Index("idx_notes_meeting_offset", "meeting_id", "recording_offset"),
    )


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    summary_text = Column(Text, nullable=False)
    action_items = Column(JSON, default=list)  # List of {text, owner, due_date}
    key_decisions = Column(JSON, default=list)  # List of {text, context}
    model_used = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    meeting = relationship("Meeting", back_populates="summary")


class CalendarConnection(Base):
    __tablename__ = "calendar_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider = Column(String(20), nullable=False)  # google, outlook
    access_token = Column(Text, nullable=False)  # Encrypted
    refresh_token = Column(Text, nullable=False)  # Encrypted
    token_expiry = Column(DateTime(timezone=True), nullable=False)
    calendar_id = Column(String(500), nullable=False)
    auto_record = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="calendar_connections")
    events = relationship(
        "CalendarEvent", back_populates="connection", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (Index("idx_calendar_conn_user_provider", "user_id", "provider"),)


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("calendar_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_event_id = Column(String(500), nullable=False)
    title = Column(String(500), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    attendees = Column(JSON, default=list)  # List of attendee emails/names
    meeting_url = Column(String(1000), nullable=True)  # Zoom/Meet/Teams link
    auto_record = Column(Boolean, default=False)
    synced_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    connection = relationship("CalendarConnection", back_populates="events")
    meetings = relationship("Meeting", back_populates="calendar_event")

    # Indexes and Constraints
    __table_args__ = (
        Index("idx_calendar_events_start", "start_time"),
        UniqueConstraint(
            "connection_id", "provider_event_id", name="uix_calendar_event"
        ),
    )


class Export(Base):
    __tablename__ = "exports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    format = Column(String(10), nullable=False)  # markdown, pdf, json
    file_path = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    meeting = relationship("Meeting", back_populates="exports")


class JobStatus(Base):
    """Track async job progress for transcription, summarization, etc."""

    __tablename__ = "job_status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_type = Column(
        String(50), nullable=False
    )  # transcription, summarization, export, etc.
    status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, processing, completed, failed
    progress = Column(Integer, default=0)  # 0-100
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
