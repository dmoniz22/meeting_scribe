from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.models.meeting import Meeting, User

router = APIRouter(prefix="/meetings", tags=["meetings"])


# Pydantic schemas
class MeetingCreate(BaseModel):
    title: str = Field(default="Untitled Meeting", max_length=500)


class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None


class MeetingResponse(BaseModel):
    id: UUID
    title: str
    status: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MeetingListResponse(BaseModel):
    items: List[MeetingResponse]
    total: int
    limit: int
    offset: int


# Get or create default user for development
async def get_or_create_default_user(db: AsyncSession):
    """Get the first user or create a default one for development."""
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            email="dev@meetscribe.local",
            display_name="Developer"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    
    return user


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    meeting_data: MeetingCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new meeting record."""
    user = await get_or_create_default_user(db)
    
    meeting = Meeting(
        user_id=user.id,
        title=meeting_data.title,
        status="idle"
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.get("", response_model=MeetingListResponse)
async def list_meetings(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List meetings with optional filtering."""
    user = await get_or_create_default_user(db)
    
    # Build query
    query = select(Meeting).where(Meeting.user_id == user.id)
    
    if status:
        query = query.where(Meeting.status == status)
    
    # Get total count
    count_query = select(Meeting.id).where(Meeting.user_id == user.id)
    if status:
        count_query = count_query.where(Meeting.status == status)
    count_result = await db.execute(count_query)
    total = len(count_result.scalars().all())
    
    # Get paginated results
    query = query.order_by(desc(Meeting.created_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    meetings = result.scalars().all()
    
    return MeetingListResponse(
        items=[MeetingResponse.model_validate(m) for m in meetings],
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific meeting by ID."""
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    return meeting


@router.put("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: UUID,
    meeting_data: MeetingUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a meeting's metadata."""
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    if meeting_data.title is not None:
        meeting.title = meeting_data.title
    if meeting_data.tags is not None:
        meeting.tags = meeting_data.tags
    
    meeting.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a meeting and all related data."""
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    await db.delete(meeting)
    await db.commit()
    return None
