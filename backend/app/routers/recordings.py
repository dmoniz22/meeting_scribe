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
import urllib.request

from app.core.database import get_db
from app.core.config import settings
from app.models.meeting import Meeting

router = APIRouter(prefix="/recordings", tags=["recordings"])

AUDIO_DAEMON_HOST = settings.AUDIO_DAEMON_HOST
AUDIO_DAEMON_PORT = settings.AUDIO_DAEMON_PORT
AUDIO_DAEMON_URL = f"http://{AUDIO_DAEMON_HOST}:{AUDIO_DAEMON_PORT}"


@router.post("/daemon/start")
async def start_audio_daemon():
    """Start the audio daemon process."""
    import subprocess
    import signal

    # Check if already running
    try:
        result = call_audio_daemon_http("GET", "/health")
        if result.get("status") == "ok":
            return {
                "status": "already_running",
                "message": "Audio daemon is already running",
            }
    except Exception:
        pass

    # Start the audio daemon
    audio_daemon_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "audio-daemon",
    )
    server_script = os.path.join(audio_daemon_dir, "server_tcp.py")

    if not os.path.exists(server_script):
        raise HTTPException(status_code=500, detail="Audio daemon script not found")

    try:
        # Start the process in background
        subprocess.Popen(
            ["python3", server_script],
            cwd=audio_daemon_dir,
            stdout=open(os.devnull, "w"),
            stderr=open(os.devnull, "w"),
            start_new_session=True,
        )

        # Wait a moment for it to start
        import asyncio

        await asyncio.sleep(2)

        return {"status": "started", "message": "Audio daemon started successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start audio daemon: {str(e)}"
        )


@router.post("/daemon/stop")
async def stop_audio_daemon():
    """Stop the audio daemon process."""
    import subprocess

    try:
        result = call_audio_daemon_http("POST", "/shutdown", {})
        return {"status": "stopped", "message": "Audio daemon stopped"}
    except Exception:
        # Try killing by PID file
        pid_file = os.path.join(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            ),
            ".audio.pid",
        )
        if os.path.exists(pid_file):
            with open(pid_file) as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                return {"status": "stopped", "message": "Audio daemon stopped"}
            except Exception:
                pass
        return {"status": "error", "message": "Could not stop audio daemon"}


@router.get("/daemon/status")
async def get_audio_daemon_status():
    """Get audio daemon status."""
    try:
        result = call_audio_daemon_http("GET", "/health")
        return {"status": "running", "details": result}
    except Exception as e:
        return {"status": "stopped", "error": str(e)}


@router.post("/daemon/restart")
async def restart_audio_routing():
    """Restart audio routing (re-setup capture paths)."""
    try:
        result = call_audio_daemon_http("POST", "/restart", {})
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/daemon/config")
async def get_daemon_config():
    """Get current audio gain configuration."""
    try:
        return call_audio_daemon_http("GET", "/config")
    except Exception as e:
        return {"system_gain": 0.5, "mic_gain": 10.0, "error": str(e)}


class DaemonConfigRequest(BaseModel):
    system_gain: Optional[float] = None
    mic_gain: Optional[float] = None


@router.post("/daemon/config")
async def set_daemon_config(request: DaemonConfigRequest):
    """Update audio gain configuration (applied on next recording)."""
    try:
        data = {}
        if request.system_gain is not None:
            data["system_gain"] = request.system_gain
        if request.mic_gain is not None:
            data["mic_gain"] = request.mic_gain
        return call_audio_daemon_http("POST", "/config", data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def call_audio_daemon_http(method: str, endpoint: str, data: dict = None) -> dict:
    """Make HTTP request to Audio Daemon via TCP."""
    url = f"{AUDIO_DAEMON_URL}{endpoint}"

    try:
        if method == "GET":
            req = urllib.request.Request(url, method="GET")
        else:
            body = json.dumps(data).encode() if data else b""
            req = urllib.request.Request(
                url,
                data=body,
                method=method,
                headers={"Content-Type": "application/json"},
            )

        with urllib.request.urlopen(req, timeout=10.0) as response:
            return json.loads(response.read().decode())

    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.read() else "{}"
        try:
            error_json = json.loads(error_body)
            raise HTTPException(
                status_code=e.code, detail=error_json.get("error", error_body)
            )
        except json.JSONDecodeError:
            raise HTTPException(status_code=e.code, detail=error_body or str(e))
    except urllib.error.URLError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Audio daemon not available at {AUDIO_DAEMON_URL}. Please ensure the audio daemon is running on the host.",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Audio daemon error: {str(e)}")


class StartRecordingRequest(BaseModel):
    meeting_id: Optional[UUID] = Field(
        None, description="Meeting ID (creates new if not provided)"
    )


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


class TranscribeRequest(BaseModel):
    meeting_id: UUID


class TranscribeResponse(BaseModel):
    success: bool
    meeting_id: UUID
    message: str


class SummarizeRequest(BaseModel):
    meeting_id: UUID


class SummarizeResponse(BaseModel):
    success: bool
    meeting_id: UUID
    message: str


@router.post("/start", response_model=StartRecordingResponse)
async def start_recording(
    request: Optional[StartRecordingRequest] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """Start recording audio for a meeting."""
    meeting_id = request.meeting_id if request else None
    if meeting_id:
        result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
        meeting = result.scalar_one_or_none()

        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")

        if meeting.status == "recording":
            raise HTTPException(status_code=400, detail="Meeting is already recording")
    else:
        from app.routers.meetings import get_or_create_default_user

        user = await get_or_create_default_user(db)

        meeting = Meeting(user_id=user.id, title="Recording Session", status="idle")
        db.add(meeting)
        await db.commit()
        await db.refresh(meeting)

    try:
        daemon_response = call_audio_daemon_http(
            "POST", "/start", {"meeting_id": str(meeting.id)}
        )

        if not daemon_response.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Audio daemon failed to start: {daemon_response.get('error')}",
            )

        meeting.status = "recording"
        meeting.started_at = datetime.utcnow()
        await db.commit()

        return StartRecordingResponse(
            success=True,
            meeting_id=meeting.id,
            started_at=daemon_response.get("started_at", datetime.utcnow().isoformat()),
            message="Recording started successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start recording: {str(e)}"
        )


@router.post("/stop", response_model=StopRecordingResponse)
async def stop_recording(db: AsyncSession = Depends(get_db)):
    """Stop the current recording."""
    from sqlalchemy import desc

    result = await db.execute(
        select(Meeting)
        .where(Meeting.status == "recording")
        .order_by(desc(Meeting.started_at))
        .limit(1)
    )
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=400, detail="No active recording found")

    try:
        daemon_response = call_audio_daemon_http("POST", "/stop")

        if not daemon_response.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Audio daemon failed to stop: {daemon_response.get('error')}",
            )

        duration = daemon_response.get("duration_seconds", 0)

        meeting.status = "recorded"
        meeting.ended_at = datetime.utcnow()
        meeting.duration_seconds = int(duration)
        meeting.audio_path = daemon_response.get("audio_path")
        await db.commit()

        return StopRecordingResponse(
            success=True,
            meeting_id=meeting.id,
            duration_seconds=duration,
            audio_path=daemon_response.get("audio_path", ""),
            message="Recording stopped successfully. Use /transcribe endpoint to start transcription.",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to stop recording: {str(e)}"
        )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_meeting(
    request: TranscribeRequest, db: AsyncSession = Depends(get_db)
):
    """Trigger transcription and embedding generation for a meeting."""
    result = await db.execute(select(Meeting).where(Meeting.id == request.meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status not in ["recorded", "transcribed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Meeting must be in 'recorded' status to transcribe. Current status: {meeting.status}",
        )

    if not meeting.audio_path:
        raise HTTPException(
            status_code=400, detail="No audio file found for this meeting"
        )

    try:
        container_audio_path = meeting.audio_path.replace(
            "/home/dmoniz/projects/meeting_transcriber/data/recordings",
            "/data/recordings",
        )

        from celery import Celery

        celery_app = Celery("meetscribe")
        celery_app.conf.broker_url = settings.REDIS_URL
        celery_app.conf.result_backend = settings.REDIS_URL
        celery_app.send_task(
            "app.tasks.transcription.transcribe_meeting",
            args=[str(meeting.id), container_audio_path],
            queue="default",
        )

        meeting.status = "transcribing"
        await db.commit()

        return TranscribeResponse(
            success=True,
            meeting_id=meeting.id,
            message="Transcription started. This will automatically generate embeddings when complete.",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger transcription: {str(e)}"
        )


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize_meeting(
    request: SummarizeRequest, db: AsyncSession = Depends(get_db)
):
    """Trigger summarization for a meeting (requires transcription)."""
    result = await db.execute(select(Meeting).where(Meeting.id == request.meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if meeting.status != "transcribed":
        raise HTTPException(
            status_code=400,
            detail=f"Meeting must be transcribed before summarization. Current status: {meeting.status}",
        )

    try:
        from celery import Celery

        celery_app = Celery("meetscribe")
        celery_app.conf.broker_url = settings.REDIS_URL
        celery_app.conf.result_backend = settings.REDIS_URL
        celery_app.send_task(
            "app.tasks.summarization.summarize_meeting",
            args=[str(meeting.id)],
            queue="default",
        )

        meeting.status = "summarizing"
        await db.commit()

        return SummarizeResponse(
            success=True, meeting_id=meeting.id, message="Summarization started."
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger summarization: {str(e)}"
        )


@router.get("/status", response_model=RecordingStatusResponse)
async def get_recording_status():
    """Get current recording status."""
    try:
        daemon_response = call_audio_daemon_http("GET", "/status")

        return RecordingStatusResponse(
            is_recording=daemon_response.get("is_recording", False),
            meeting_id=UUID(daemon_response["meeting_id"])
            if daemon_response.get("meeting_id")
            else None,
            started_at=daemon_response.get("started_at"),
            duration_seconds=daemon_response.get("duration_seconds"),
            rms_system=daemon_response.get("rms_system"),
            rms_mic=daemon_response.get("rms_mic"),
        )

    except HTTPException as e:
        if e.status_code == 503:
            return RecordingStatusResponse(is_recording=False)
        raise


from fastapi.responses import FileResponse

# Host to container path mapping
HOST_RECORDINGS_PATH = "/home/dmoniz/projects/meeting_transcriber/data/recordings"
CONTAINER_RECORDINGS_PATH = "/data/recordings"


def convert_host_to_container_path(host_path: str) -> str:
    """Convert host path to container path for audio files."""
    if not host_path:
        return host_path
    if host_path.startswith(HOST_RECORDINGS_PATH):
        return host_path.replace(HOST_RECORDINGS_PATH, CONTAINER_RECORDINGS_PATH)
    return host_path


@router.get("/audio/{meeting_id}")
async def get_audio_file(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    """Serve the audio file for a meeting."""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    if not meeting.audio_path:
        raise HTTPException(status_code=404, detail="Audio file not found")

    # Convert host path to container path
    container_path = convert_host_to_container_path(meeting.audio_path)
    if not os.path.exists(container_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(container_path, media_type="audio/wav")
