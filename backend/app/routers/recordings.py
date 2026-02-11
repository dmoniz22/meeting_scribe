from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
import json
import socket
import os

from app.core.database import get_db
from app.core.config import settings
from app.models.meeting import Meeting

router = APIRouter(prefix="/recordings", tags=["recordings"])

# Audio Daemon connection
AUDIO_DAEMON_SOCKET = settings.AUDIO_DAEMON_SOCKET


class UnixSocketHTTP:
    """Simple HTTP client for Unix sockets."""
    
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
    
    def request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make HTTP request over Unix socket."""
        import io
        
        # Create socket connection
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.socket_path)
            sock.settimeout(10.0)
            
            # Build HTTP request
            body = json.dumps(data).encode() if data else b""
            request_lines = [
                f"{method} {endpoint} HTTP/1.1",
                f"Host: localhost",
                f"Content-Type: application/json",
                f"Content-Length: {len(body)}",
                "Connection: close",
                "",
                ""
            ]
            request = "\r\n".join(request_lines).encode() + body
            
            # Send request
            sock.sendall(request)
            
            # Receive response
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            
            # Parse response
            response_text = response.decode('utf-8', errors='ignore')
            
            # Split headers and body
            if '\r\n\r\n' in response_text:
                headers, body = response_text.split('\r\n\r\n', 1)
            elif '\n\n' in response_text:
                headers, body = response_text.split('\n\n', 1)
            else:
                raise Exception("Invalid HTTP response")
            
            # Parse JSON body
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                raise Exception(f"Invalid JSON response: {body[:200]}")
                
        finally:
            sock.close()


async def call_audio_daemon(method: str, endpoint: str, data: dict = None) -> dict:
    """Make HTTP request to Audio Daemon via Unix socket."""
    socket_path = AUDIO_DAEMON_SOCKET
    
    # Check if socket exists
    if not os.path.exists(socket_path):
        raise HTTPException(
            status_code=503,
            detail="Audio daemon not available. Please ensure the audio daemon is running on the host."
        )
    
    try:
        client = UnixSocketHTTP(socket_path)
        return client.request(method, endpoint, data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Audio daemon error: {str(e)}"
        )


# Schemas
class StartRecordingRequest(BaseModel):
    meeting_id: Optional[UUID] = Field(None, description="Meeting ID (creates new if not provided)")


class StartRecordingResponse(BaseModel):
    success: bool
    meeting_id: UUID
    started_at: str
    message: str


class StopRecordingResponse(BaseModel):
    success: bool
    meeting_id: UUID
    duration_seconds: float
    audio_path: str
    message: str


class RecordingStatusResponse(BaseModel):
    is_recording: bool
    meeting_id: Optional[UUID] = None
    started_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    rms_system: Optional[float] = None
    rms_mic: Optional[float] = None


@router.post("/start", response_model=StartRecordingResponse)
async def start_recording(
    request: StartRecordingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Start recording audio for a meeting."""
    # Get or create meeting
    if request.meeting_id:
        # Use existing meeting
        result = await db.execute(
            select(Meeting).where(Meeting.id == request.meeting_id)
        )
        meeting = result.scalar_one_or_none()
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if meeting.status == "recording":
            raise HTTPException(status_code=400, detail="Meeting is already recording")
    else:
        # Create new meeting
        from app.routers.meetings import get_or_create_default_user
        user = await get_or_create_default_user(db)
        
        meeting = Meeting(
            user_id=user.id,
            title="Recording Session",
            status="idle"
        )
        db.add(meeting)
        await db.commit()
        await db.refresh(meeting)
    
    # Call audio daemon to start recording
    try:
        daemon_response = await call_audio_daemon(
            "POST",
            "/start",
            {"meeting_id": str(meeting.id)}
        )
        
        if not daemon_response.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Audio daemon failed to start: {daemon_response.get('error')}"
            )
        
        # Update meeting status
        meeting.status = "recording"
        meeting.started_at = datetime.utcnow()
        await db.commit()
        
        return StartRecordingResponse(
            success=True,
            meeting_id=meeting.id,
            started_at=daemon_response.get("started_at", datetime.utcnow().isoformat()),
            message="Recording started successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start recording: {str(e)}"
        )


@router.post("/stop", response_model=StopRecordingResponse)
async def stop_recording(db: AsyncSession = Depends(get_db)):
    """Stop the current recording."""
    # Find the currently recording meeting
    result = await db.execute(
        select(Meeting).where(Meeting.status == "recording")
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=400, detail="No active recording found")
    
    # Call audio daemon to stop recording
    try:
        daemon_response = await call_audio_daemon("POST", "/stop")
        
        if not daemon_response.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Audio daemon failed to stop: {daemon_response.get('error')}"
            )
        
        # Calculate duration
        duration = daemon_response.get("duration_seconds", 0)
        
        # Update meeting status
        meeting.status = "processing"  # Will be changed to "completed" after transcription
        meeting.ended_at = datetime.utcnow()
        meeting.duration_seconds = int(duration)
        meeting.audio_path = daemon_response.get("audio_path")
        await db.commit()
        
        # Trigger transcription task using Celery
        audio_path = daemon_response.get("audio_path")
        if audio_path:
            from celery import Celery
            # Convert host path to container path
            container_audio_path = audio_path.replace(
                "/home/dmoniz/projects/meeting_transcriber/data/recordings",
                "/data/recordings"
            )
            celery_app = Celery('meetscribe')
            celery_app.conf.broker_url = settings.REDIS_URL
            celery_app.conf.result_backend = settings.REDIS_URL
            celery_app.send_task(
                'app.tasks.transcription.transcribe_meeting',
                args=[str(meeting.id), container_audio_path],
                queue='default'
            )
            print(f"Triggered transcription task for meeting {meeting.id}")
        
        return StopRecordingResponse(
            success=True,
            meeting_id=meeting.id,
            duration_seconds=duration,
            audio_path=daemon_response.get("audio_path", ""),
            message="Recording stopped successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop recording: {str(e)}"
        )


@router.get("/status", response_model=RecordingStatusResponse)
async def get_recording_status():
    """Get current recording status."""
    try:
        daemon_response = await call_audio_daemon("GET", "/status")
        
        return RecordingStatusResponse(
            is_recording=daemon_response.get("is_recording", False),
            meeting_id=UUID(daemon_response["meeting_id"]) if daemon_response.get("meeting_id") else None,
            started_at=daemon_response.get("started_at"),
            duration_seconds=daemon_response.get("duration_seconds"),
            rms_system=daemon_response.get("rms_system"),
            rms_mic=daemon_response.get("rms_mic")
        )
        
    except HTTPException as e:
        # If daemon is not available, return not recording
        if e.status_code == 503:
            return RecordingStatusResponse(is_recording=False)
        raise
