from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload
from typing import List
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.models.meeting import Meeting, Note, TranscriptSegment, Summary
from app.routers.meetings import get_or_create_default_user

router = APIRouter(prefix="/meetings", tags=["meetings"])


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1)
    recording_offset: float = Field(default=0.0, ge=0)
    note_type: str = Field(default="general")


class NoteResponse(BaseModel):
    id: UUID
    content: str
    recording_offset: float
    note_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class TranscriptSegmentResponse(BaseModel):
    id: UUID
    speaker_label: str | None
    speaker_name: str | None
    start_time: float
    end_time: float
    text: str
    confidence: float | None
    
    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    id: UUID
    summary_text: str
    action_items: List[dict]
    key_decisions: List[dict]
    model_used: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class MeetingDetailResponse(BaseModel):
    id: UUID
    title: str
    status: str
    started_at: datetime | None
    ended_at: datetime | None
    duration_seconds: int | None
    audio_path: str | None
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    transcript_segments: List[TranscriptSegmentResponse]
    notes: List[NoteResponse]
    summary: SummaryResponse | None
    
    class Config:
        from_attributes = True


@router.get("/{meeting_id}/detail", response_model=MeetingDetailResponse)
async def get_meeting_detail(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get full meeting details including transcript, notes, and summary."""
    # Load meeting with summary eagerly
    result = await db.execute(
        select(Meeting)
        .options(joinedload(Meeting.summary))
        .where(Meeting.id == meeting_id)
    )
    meeting = result.unique().scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Get transcript segments with speaker info
    transcript_result = await db.execute(
        select(TranscriptSegment)
        .options(joinedload(TranscriptSegment.speaker))
        .where(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.start_time)
    )
    segments = transcript_result.unique().scalars().all()
    
    transcript_list = []
    for seg in segments:
        speaker_label = seg.speaker.label if seg.speaker else None
        speaker_name = seg.speaker.display_name if seg.speaker else None
        
        transcript_list.append(TranscriptSegmentResponse(
            id=seg.id,
            speaker_label=speaker_label,
            speaker_name=speaker_name,
            start_time=seg.start_time,
            end_time=seg.end_time,
            text=seg.text,
            confidence=seg.confidence
        ))
    
    # Get notes
    notes_result = await db.execute(
        select(Note).where(Note.meeting_id == meeting_id).order_by(desc(Note.created_at))
    )
    notes = notes_result.scalars().all()
    
    # Build summary response
    summary = None
    if meeting.summary:
        summary = SummaryResponse(
            id=meeting.summary.id,
            summary_text=meeting.summary.summary_text,
            action_items=meeting.summary.action_items or [],
            key_decisions=meeting.summary.key_decisions or [],
            model_used=meeting.summary.model_used,
            created_at=meeting.summary.created_at
        )
    
    return MeetingDetailResponse(
        id=meeting.id,
        title=meeting.title,
        status=meeting.status,
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        duration_seconds=meeting.duration_seconds,
        audio_path=meeting.audio_path,
        tags=meeting.tags or [],
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
        transcript_segments=transcript_list,
        notes=[NoteResponse.model_validate(n) for n in notes],
        summary=summary
    )


@router.post("/{meeting_id}/notes", response_model=NoteResponse, status_code=201)
async def create_note(meeting_id: UUID, note_data: NoteCreate, db: AsyncSession = Depends(get_db)):
    """Add a note to a meeting."""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    user = await get_or_create_default_user(db)
    
    note = Note(
        meeting_id=meeting_id,
        user_id=user.id,
        content=note_data.content,
        recording_offset=note_data.recording_offset,
        note_type=note_data.note_type
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    
    return note


@router.delete("/{meeting_id}/notes/{note_id}", status_code=204)
async def delete_note(meeting_id: UUID, note_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a note."""
    result = await db.execute(
        select(Note).where(Note.id == note_id).where(Note.meeting_id == meeting_id)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    await db.delete(note)
    await db.commit()
    return None
