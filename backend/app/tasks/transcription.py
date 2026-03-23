#!/usr/bin/env python3
"""
transcription.py - WhisperX transcription task with speaker diarization

This task transcribes audio files using WhisperX with:
- faster-whisper backend for efficient transcription
- pyannote.audio for speaker diarization
- GPU memory management with sequential processing
"""

import gc
import torch
from pathlib import Path
from typing import Dict, Optional
from uuid import UUID
import json

import whisperx
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.core.config import settings
from app.core.sessions import get_session_factory
from app.models.meeting import Meeting, TranscriptSegment, Speaker


AsyncSessionLocal = get_session_factory()


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
                settings.REDIS_URL, decode_responses=True
            )
        except Exception as e:
            print(f"Warning: Could not connect to Redis: {e}")

    def update_progress(
        self,
        job_type: str,
        progress: int,
        status: str = "processing",
        result: dict = None,
    ):
        """Update job progress in Redis."""
        if self.redis_client:
            data = {
                "meeting_id": self.meeting_id,
                "job_type": job_type,
                "progress": progress,
                "status": status,
            }
            if result:
                data["result"] = json.dumps(result)

            channel = f"meeting:{self.meeting_id}:jobs"
            self.redis_client.publish(channel, json.dumps(data))

            key = f"job:{self.meeting_id}:{job_type}"
            self.redis_client.hset(key, mapping=data)
            self.redis_client.expire(key, 3600)


def clear_gpu_memory():
    """Clear GPU memory between model switches."""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
    gc.collect()


async def save_transcription_results(meeting_id: str, result: dict):
    """Save transcription results to database."""
    async with AsyncSessionLocal() as session:
        try:
            meeting_uuid = UUID(meeting_id)

            meeting_result = await session.execute(
                select(Meeting).where(Meeting.id == meeting_uuid)
            )
            meeting = meeting_result.scalar_one_or_none()

            if not meeting:
                raise ValueError(f"Meeting not found: {meeting_id}")

            speakers_dict = {}
            colors = [
                "#3B82F6",
                "#EF4444",
                "#10B981",
                "#F59E0B",
                "#8B5CF6",
                "#EC4899",
                "#06B6D4",
                "#84CC16",
            ]

            for segment in result["segments"]:
                speaker_label = segment.get("speaker", "SPEAKER_00")
                if speaker_label not in speakers_dict:
                    color_idx = len(speakers_dict) % len(colors)
                    speaker = Speaker(
                        meeting_id=meeting_uuid,
                        label=speaker_label,
                        color=colors[color_idx],
                    )
                    session.add(speaker)
                    speakers_dict[speaker_label] = speaker

            await session.flush()

            for segment in result["segments"]:
                speaker_label = segment.get("speaker", "SPEAKER_00")
                speaker = speakers_dict.get(speaker_label)

                transcript_segment = TranscriptSegment(
                    meeting_id=meeting_uuid,
                    speaker_id=speaker.id if speaker else None,
                    start_time=segment["start"],
                    end_time=segment["end"],
                    text=segment["text"].strip(),
                    confidence=segment.get("confidence", 1.0),
                )
                session.add(transcript_segment)

            meeting.status = "transcribed"

            await session.commit()

        except Exception as e:
            await session.rollback()
            raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def transcribe_meeting(self, meeting_id: str, audio_path: str):
    """
    Transcribe meeting audio with WhisperX and speaker diarization.

    Process:
    1. Load WhisperX model and transcribe
    2. Unload WhisperX, load diarization model
    3. Assign speaker labels to segments
    4. Store results in database
    5. Trigger embedding generation (via callback)

    Args:
        meeting_id: UUID of the meeting
        audio_path: Path to the audio file
    """
    import asyncio
    from sqlalchemy import select

    print(f"\n{'=' * 60}")
    print(f"Starting transcription for meeting: {meeting_id}")
    print(f"Audio file: {audio_path}")
    print(f"{'=' * 60}\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    job = TranscriptionJob(meeting_id)

    audio_file = Path(audio_path)
    if not audio_file.exists():
        error_msg = f"Audio file not found: {audio_path}"
        print(f"✗ {error_msg}")
        job.update_progress("transcription", 0, "failed", {"error": error_msg})
        raise FileNotFoundError(error_msg)

    try:
        print("Step 1/3: Loading WhisperX model...")
        job.update_progress(
            "transcription", 10, "processing", {"step": "loading_model"}
        )

        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = (
            settings.WHISPER_COMPUTE_TYPE if torch.cuda.is_available() else "int8"
        )

        print(f"  Device: {device}")
        print(f"  Compute type: {compute_type}")
        print(f"  Model: {settings.WHISPER_MODEL}")

        if settings.HF_TOKEN:
            import os

            os.environ["HF_TOKEN"] = settings.HF_TOKEN

        from faster_whisper import WhisperModel

        model = WhisperModel(
            settings.WHISPER_MODEL,
            device=device,
            compute_type=compute_type,
        )

        print("  ✓ Model loaded")
        job.update_progress("transcription", 20, "processing", {"step": "transcribing"})

        print("\n  Loading audio...")
        import soundfile as sf
        import numpy as np

        audio_data, sr = sf.read(str(audio_file))
        if sr != 16000:
            import resampy

            audio_data = resampy.resample(audio_data.astype(float), sr, 16000).astype(
                np.float32
            )
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)
        audio = audio_data.astype(np.float32)

        print("  Transcribing...")
        segments_iter, info = model.transcribe(
            audio, language="en", word_timestamps=True
        )
        segments = []
        for seg in segments_iter:
            segments.append(
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                }
            )

        result = {"segments": segments, "language": info.language}
        print(f"  ✓ Transcription complete: {len(result['segments'])} segments")
        job.update_progress(
            "transcription",
            50,
            "processing",
            {
                "step": "transcription_complete",
                "segments_count": len(result["segments"]),
            },
        )

        print("\n  Unloading WhisperX model...")
        del model
        clear_gpu_memory()
        print("  ✓ Model unloaded")

        print("\nStep 2/3: Aligning timestamps...")
        job.update_progress("transcription", 60, "processing", {"step": "aligning"})

        try:
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"], device=device
            )
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )
            del model_a
            clear_gpu_memory()
            print("  ✓ Alignment complete")
        except Exception as e:
            print(f"  ⚠ Alignment skipped: {e}")

        print("\nStep 3/3: Speaker diarization...")
        job.update_progress("transcription", 70, "processing", {"step": "diarizing"})

        if settings.HF_TOKEN:
            try:
                diarize_model = whisperx.DiarizationPipeline(
                    model_name="pyannote/speaker-diarization-3.1",
                    use_auth_token=settings.HF_TOKEN,
                    device=device,
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

        print("\n  Saving to database...")
        loop.run_until_complete(save_transcription_results(meeting_id, result))
        print("  ✓ Results saved")

        job.update_progress(
            "transcription",
            100,
            "completed",
            {
                "segments_count": len(result["segments"]),
                "language": result.get("language", "unknown"),
            },
        )

        print(f"\n{'=' * 60}")
        print("✓ Transcription complete!")
        print(f"{'=' * 60}\n")

        from app.tasks.embeddings import generate_embeddings

        generate_embeddings.delay(meeting_id)

        return {
            "success": True,
            "meeting_id": meeting_id,
            "segments_count": len(result["segments"]),
            "language": result.get("language", "unknown"),
        }

    except Exception as e:
        error_msg = str(e)
        print(f"\n✗ Transcription failed: {error_msg}")
        job.update_progress("transcription", 0, "failed", {"error": error_msg})

        try:
            self.retry(countdown=60)
        except MaxRetriesExceededError:
            print("Max retries exceeded, marking as failed")
            raise
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except:
            pass
        asyncio.set_event_loop(None)
