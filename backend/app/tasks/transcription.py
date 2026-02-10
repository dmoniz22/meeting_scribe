#!/usr/bin/env python3
"""
transcription.py - WhisperX transcription task with speaker diarization

This task transcribes audio files using WhisperX with:
- faster-whisper backend for efficient transcription
- pyannote.audio for speaker diarization
- GPU memory management with sequential processing
"""

import os
import gc
import torch
from pathlib import Path
from typing import List, Dict, Optional
from uuid import UUID
import json

import whisperx
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.models.meeting import Meeting, TranscriptSegment, Speaker, JobStatus

# Database setup for sync operations in Celery
DATABASE_URL_SYNC = settings.DATABASE_URL.replace("+asyncpg", "")
engine = create_async_engine(settings.DATABASE_URL, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class TranscriptionJob:
    """Manages transcription job state and progress."""
    
    def __init__(self, meeting_id: str):
        self.meeting_id = meeting_id
        self.redis_client = None
        self._init_redis()
    
    def _init_redis(self):
        """Initialize Redis connection for progress tracking."""
        try:
            import redis
            self.redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        except Exception as e:
            print(f"Warning: Could not connect to Redis: {e}")
    
    def update_progress(self, job_type: str, progress: int, status: str = "processing", result: dict = None):
        """Update job progress in Redis."""
        if self.redis_client:
            data = {
                "meeting_id": self.meeting_id,
                "job_type": job_type,
                "progress": progress,
                "status": status
            }
            if result:
                data["result"] = json.dumps(result)
            
            # Publish to channel for WebSocket
            channel = f"meeting:{self.meeting_id}:jobs"
            self.redis_client.publish(channel, json.dumps(data))
            
            # Store in key for persistence
            key = f"job:{self.meeting_id}:{job_type}"
            self.redis_client.hset(key, mapping=data)
            self.redis_client.expire(key, 3600)  # 1 hour expiry


def clear_gpu_memory():
    """Clear GPU memory between model switches."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    gc.collect()


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def transcribe_meeting(self, meeting_id: str, audio_path: str):
    """
    Transcribe meeting audio with WhisperX and speaker diarization.
    
    Process:
    1. Load WhisperX model and transcribe
    2. Unload WhisperX, load diarization model
    3. Assign speaker labels to segments
    4. Store results in database
    5. Trigger embedding generation
    
    Args:
        meeting_id: UUID of the meeting
        audio_path: Path to the audio file
    """
    import asyncio
    
    print(f"\n{'='*60}")
    print(f"Starting transcription for meeting: {meeting_id}")
    print(f"Audio file: {audio_path}")
    print(f"{'='*60}\n")
    
    job = TranscriptionJob(meeting_id)
    
    # Check if audio file exists
    audio_file = Path(audio_path)
    if not audio_file.exists():
        error_msg = f"Audio file not found: {audio_path}"
        print(f"✗ {error_msg}")
        job.update_progress("transcription", 0, "failed", {"error": error_msg})
        raise FileNotFoundError(error_msg)
    
    try:
        # Step 1: Transcription with WhisperX
        print("Step 1/3: Loading WhisperX model...")
        job.update_progress("transcription", 10, "processing", {"step": "loading_model"})
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = settings.WHISPER_COMPUTE_TYPE if torch.cuda.is_available() else "int8"
        
        print(f"  Device: {device}")
        print(f"  Compute type: {compute_type}")
        print(f"  Model: {settings.WHISPER_MODEL}")
        
        # Load WhisperX model
        model = whisperx.load_model(
            settings.WHISPER_MODEL,
            device=device,
            compute_type=compute_type,
            language="en"  # Auto-detect if None
        )
        
        print("  ✓ Model loaded")
        job.update_progress("transcription", 20, "processing", {"step": "transcribing"})
        
        # Load audio
        print("\n  Loading audio...")
        audio = whisperx.load_audio(str(audio_file))
        
        # Transcribe
        print("  Transcribing...")
        result = model.transcribe(
            audio,
            batch_size=settings.WHISPER_BATCH_SIZE
        )
        
        print(f"  ✓ Transcription complete: {len(result['segments'])} segments")
        job.update_progress("transcription", 50, "processing", {
            "step": "transcription_complete",
            "segments_count": len(result["segments"])
        })
        
        # Unload WhisperX model to free GPU memory
        print("\n  Unloading WhisperX model...")
        del model
        clear_gpu_memory()
        print("  ✓ Model unloaded")
        
        # Step 2: Align timestamps (optional but improves accuracy)
        print("\nStep 2/3: Aligning timestamps...")
        job.update_progress("transcription", 60, "processing", {"step": "aligning"})
        
        model_a, metadata = whisperx.load_align_model(
            language_code=result["language"],
            device=device
        )
        result = whisperx.align(
            result["segments"],
            model_a,
            metadata,
            audio,
            device,
            return_char_alignments=False
        )
        
        del model_a
        clear_gpu_memory()
        print("  ✓ Alignment complete")
        
        # Step 3: Speaker Diarization
        print("\nStep 3/3: Speaker diarization...")
        job.update_progress("transcription", 70, "processing", {"step": "diarizing"})
        
        if settings.HF_TOKEN:
            try:
                diarize_model = whisperx.DiarizationPipeline(
                    model_name="pyannote/speaker-diarization-3.1",
                    use_auth_token=settings.HF_TOKEN,
                    device=device
                )
                
                diarize_segments = diarize_model(audio)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                
                del diarize_model
                clear_gpu_memory()
                print("  ✓ Diarization complete")
            except Exception as e:
                print(f"  ⚠ Diarization failed: {e}")
                print("  Continuing without speaker labels")
        else:
            print("  ⚠ No HF_TOKEN provided, skipping diarization")
        
        job.update_progress("transcription", 90, "processing", {"step": "saving"})
        
        # Step 4: Store in database
        print("\n  Saving to database...")
        asyncio.run(save_transcription_results(meeting_id, result))
        print("  ✓ Results saved")
        
        job.update_progress("transcription", 100, "completed", {
            "segments_count": len(result["segments"]),
            "language": result.get("language", "unknown")
        })
        
        print(f"\n{'='*60}")
        print("✓ Transcription complete!")
        print(f"{'='*60}\n")
        
        # Trigger embedding generation
        from app.tasks.embeddings import generate_embeddings
        generate_embeddings.delay(meeting_id)
        
        return {
            "success": True,
            "meeting_id": meeting_id,
            "segments_count": len(result["segments"]),
            "language": result.get("language", "unknown")
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"\n✗ Transcription failed: {error_msg}")
        job.update_progress("transcription", 0, "failed", {"error": error_msg})
        
        # Retry on failure
        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            print("Max retries exceeded, marking as failed")
            raise


async def save_transcription_results(meeting_id: str, result: dict):
    """Save transcription results to database."""
    async with AsyncSessionLocal() as session:
        try:
            meeting_uuid = UUID(meeting_id)
            
            # Get meeting
            meeting_result = await session.execute(
                select(Meeting).where(Meeting.id == meeting_uuid)
            )
            meeting = meeting_result.scalar_one_or_none()
            
            if not meeting:
                raise ValueError(f"Meeting not found: {meeting_id}")
            
            # Collect unique speakers
            speakers_dict = {}
            colors = ["#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4", "#84CC16"]
            
            for segment in result["segments"]:
                speaker_label = segment.get("speaker", "SPEAKER_00")
                if speaker_label not in speakers_dict:
                    color_idx = len(speakers_dict) % len(colors)
                    speaker = Speaker(
                        meeting_id=meeting_uuid,
                        label=speaker_label,
                        color=colors[color_idx]
                    )
                    session.add(speaker)
                    speakers_dict[speaker_label] = speaker
            
            await session.flush()  # Get speaker IDs
            
            # Create transcript segments
            for segment in result["segments"]:
                speaker_label = segment.get("speaker", "SPEAKER_00")
                speaker = speakers_dict.get(speaker_label)
                
                transcript_segment = TranscriptSegment(
                    meeting_id=meeting_uuid,
                    speaker_id=speaker.id if speaker else None,
                    start_time=segment["start"],
                    end_time=segment["end"],
                    text=segment["text"].strip(),
                    confidence=segment.get("confidence", 1.0)
                )
                session.add(transcript_segment)
            
            # Update meeting status
            meeting.status = "completed"
            
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            raise


# Make sure to create async engine
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine(settings.DATABASE_URL, future=True, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
