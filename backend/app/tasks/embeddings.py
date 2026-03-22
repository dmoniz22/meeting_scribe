#!/usr/bin/env python3
"""
embeddings.py - Generate sentence embeddings for transcript segments and notes

Uses sentence-transformers/all-MiniLM-L6-v2 for 384-dimensional embeddings.
"""

import gc
import torch
import numpy as np
from typing import List
from uuid import UUID
from celery import shared_task
from sqlalchemy import select

from app.core.config import settings
from app.core.sessions import get_session_factory
from app.models.meeting import TranscriptSegment, Note, Meeting

AsyncSessionLocal = get_session_factory()

_embedding_model = None


def get_embedding_model():
    """Lazy load the embedding model."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        print(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        print("✓ Embedding model loaded")
    return _embedding_model


def clear_embedding_model():
    """Clear embedding model from memory."""
    global _embedding_model
    if _embedding_model is not None:
        del _embedding_model
        _embedding_model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        print("✓ Embedding model unloaded")


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def generate_embeddings(self, meeting_id: str):
    """
    Generate embeddings for all transcript segments and notes in a meeting.

    Args:
        meeting_id: UUID of the meeting
    """
    import asyncio

    print(f"\n{'=' * 60}")
    print(f"Generating embeddings for meeting: {meeting_id}")
    print(f"{'=' * 60}\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        model = get_embedding_model()

        result = loop.run_until_complete(_generate_embeddings_async(meeting_id, model))

        print(f"\n{'=' * 60}")
        print(
            f"✓ Embeddings generated: {result['segments']} segments, {result['notes']} notes"
        )
        print(f"{'=' * 60}\n")

        return result

    except Exception as e:
        print(f"✗ Error generating embeddings: {e}")
        raise self.retry(exc=e)
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except:
            pass
        asyncio.set_event_loop(None)


async def _generate_embeddings_async(meeting_id: str, model):
    """Async function to generate and save embeddings."""
    async with AsyncSessionLocal() as session:
        try:
            meeting_uuid = UUID(meeting_id)

            segments_result = await session.execute(
                select(TranscriptSegment).where(
                    TranscriptSegment.meeting_id == meeting_uuid,
                    TranscriptSegment.embedding.is_(None),
                )
            )
            segments = segments_result.scalars().all()

            print(f"Processing {len(segments)} transcript segments...")

            batch_size = 32
            for i in range(0, len(segments), batch_size):
                batch = segments[i : i + batch_size]
                texts = [seg.text for seg in batch]

                embeddings = model.encode(texts, convert_to_numpy=True)

                for seg, embedding in zip(batch, embeddings):
                    seg.embedding = embedding.tolist()

                if (i + batch_size) % 100 == 0:
                    print(
                        f"  Processed {min(i + batch_size, len(segments))}/{len(segments)} segments"
                    )

            notes_result = await session.execute(
                select(Note).where(
                    Note.meeting_id == meeting_uuid, Note.embedding.is_(None)
                )
            )
            notes = notes_result.scalars().all()

            print(f"Processing {len(notes)} notes...")

            for i in range(0, len(notes), batch_size):
                batch = notes[i : i + batch_size]
                texts = [note.content for note in batch]

                embeddings = model.encode(texts, convert_to_numpy=True)

                for note, embedding in zip(batch, embeddings):
                    note.embedding = embedding.tolist()

            await session.commit()

            return {
                "success": True,
                "meeting_id": meeting_id,
                "segments": len(segments),
                "notes": len(notes),
            }

        except Exception as e:
            await session.rollback()
            raise
