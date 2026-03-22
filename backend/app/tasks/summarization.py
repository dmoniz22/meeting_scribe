#!/usr/bin/env python3
"""
summarization.py - Generate meeting summaries using Ollama

Uses local LLM via Ollama API to generate:
- Executive summary
- Action items
- Key decisions
"""

import json
import httpx
from typing import Dict
from uuid import UUID
from celery import shared_task
from sqlalchemy import select, update

from app.core.config import settings
from app.core.sessions import get_session_factory
from app.models.meeting import Meeting, TranscriptSegment, Note, Summary

AsyncSessionLocal = get_session_factory()

OLLAMA_API_URL = f"{settings.OLLAMA_BASE_URL}/api/generate"


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def summarize_meeting(self, meeting_id: str):
    """
    Generate meeting summary using Ollama.

    Args:
        meeting_id: UUID of the meeting
    """
    import asyncio

    print(f"\n{'=' * 60}")
    print(f"Generating summary for meeting: {meeting_id}")
    print(f"Model: {settings.OLLAMA_MODEL}")
    print(f"{'=' * 60}\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        transcript_data = loop.run_until_complete(_fetch_meeting_data(meeting_id))

        if not transcript_data["segments"]:
            print("⚠ No transcript segments found, skipping summarization")
            return {"success": False, "error": "No transcript available"}

        transcript_text = _build_transcript_text(transcript_data["segments"])
        notes_text = _build_notes_text(transcript_data["notes"])

        summary_result = _generate_summary_with_ollama(transcript_text, notes_text)

        loop.run_until_complete(_save_summary(meeting_id, summary_result))

        print(f"\n{'=' * 60}")
        print("✓ Summary generated successfully")
        print(f"{'=' * 60}\n")

        return {
            "success": True,
            "meeting_id": meeting_id,
            "model_used": settings.OLLAMA_MODEL,
        }

    except Exception as e:
        print(f"✗ Error generating summary: {e}")
        raise self.retry(exc=e)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except:
            pass
        asyncio.set_event_loop(None)


async def _fetch_meeting_data(meeting_id: str) -> Dict:
    """Fetch transcript segments and notes for a meeting."""
    async with AsyncSessionLocal() as session:
        meeting_uuid = UUID(meeting_id)

        segments_result = await session.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.meeting_id == meeting_uuid)
            .order_by(TranscriptSegment.start_time)
        )
        segments = segments_result.scalars().all()

        notes_result = await session.execute(
            select(Note)
            .where(Note.meeting_id == meeting_uuid)
            .order_by(Note.recording_offset)
        )
        notes = notes_result.scalars().all()

        return {"segments": segments, "notes": notes}


def _build_transcript_text(segments) -> str:
    """Build formatted transcript text."""
    lines = []
    for seg in segments:
        speaker = seg.speaker.label if seg.speaker else "Unknown"
        timestamp = _format_timestamp(seg.start_time)
        lines.append(f"[{timestamp}] {speaker}: {seg.text}")
    return "\n".join(lines)


def _build_notes_text(notes) -> str:
    """Build formatted notes text."""
    if not notes:
        return "No notes were taken during this meeting."

    lines = []
    for note in notes:
        timestamp = _format_timestamp(note.recording_offset)
        lines.append(f"[{timestamp}] ({note.note_type}): {note.content}")
    return "\n".join(lines)


def _format_timestamp(seconds: float) -> str:
    """Format seconds as MM:SS."""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"


def _generate_summary_with_ollama(transcript: str, notes: str) -> Dict:
    """Generate summary using Ollama API."""

    max_chars = 15000
    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n[...transcript truncated...]"

    prompt = f"""You are an AI assistant that creates structured meeting summaries.

Analyze the following meeting transcript and notes, then provide a structured summary in JSON format.

MEETING TRANSCRIPT:
{transcript}

USER NOTES:
{notes}

Provide your response in this exact JSON format:
{{
  "summary": "A concise 2-3 paragraph executive summary of the meeting",
  "action_items": [
    {{
      "text": "Description of the action item",
      "owner": "Who should do it (if mentioned, otherwise null)",
      "due_date": "Due date if mentioned (YYYY-MM-DD format or null)"
    }}
  ],
  "key_decisions": [
    {{
      "text": "Description of the decision",
      "context": "Brief context about why this decision was made"
    }}
  ]
}}

Important:
- Action items should be specific and actionable
- If no action items or decisions were made, use empty arrays []
- Only include information that was actually discussed
- Be concise but comprehensive"""

    try:
        response = httpx.post(
            OLLAMA_API_URL,
            json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=300.0,
        )
        response.raise_for_status()

        result = response.json()
        generated_text = result.get("response", "")

        try:
            json_start = generated_text.find("{")
            json_end = generated_text.rfind("}") + 1

            if json_start >= 0 and json_end > json_start:
                json_str = generated_text[json_start:json_end]
                parsed = json.loads(json_str)
            else:
                parsed = {
                    "summary": generated_text[:1000],
                    "action_items": [],
                    "key_decisions": [],
                }

            return parsed

        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse JSON response: {e}")
            return {
                "summary": generated_text[:1000]
                if generated_text
                else "Summary generation incomplete",
                "action_items": [],
                "key_decisions": [],
            }

    except httpx.TimeoutException:
        print("⚠ Ollama request timed out")
        return {
            "summary": "Summary generation timed out. The transcript may be too long.",
            "action_items": [],
            "key_decisions": [],
        }
    except Exception as e:
        print(f"✗ Error calling Ollama: {e}")
        raise


async def _save_summary(meeting_id: str, summary_data: Dict):
    """Save summary to database."""
    async with AsyncSessionLocal() as session:
        try:
            meeting_uuid = UUID(meeting_id)

            existing = await session.execute(
                select(Summary).where(Summary.meeting_id == meeting_uuid)
            )
            if existing.scalar_one_or_none():
                await session.execute(
                    update(Summary)
                    .where(Summary.meeting_id == meeting_uuid)
                    .values(
                        summary_text=summary_data.get("summary", ""),
                        action_items=summary_data.get("action_items", []),
                        key_decisions=summary_data.get("key_decisions", []),
                        model_used=settings.OLLAMA_MODEL,
                    )
                )
            else:
                summary = Summary(
                    meeting_id=meeting_uuid,
                    summary_text=summary_data.get("summary", ""),
                    action_items=summary_data.get("action_items", []),
                    key_decisions=summary_data.get("key_decisions", []),
                    model_used=settings.OLLAMA_MODEL,
                )
                session.add(summary)

            await session.commit()

        except Exception as e:
            await session.rollback()
            raise
