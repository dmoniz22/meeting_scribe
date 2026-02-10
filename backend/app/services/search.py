#!/usr/bin/env python3
"""
search.py - Hybrid search implementation

Combines:
1. Keyword search using PostgreSQL trigram similarity
2. Semantic search using pgvector cosine similarity
3. Reciprocal Rank Fusion (RRF) for merging results
"""

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.meeting import TranscriptSegment, Note, Meeting


class SearchResult(BaseModel):
    """Single search result."""
    meeting_id: UUID
    meeting_title: str
    segment_id: Optional[UUID] = None
    note_id: Optional[UUID] = None
    text: str
    timestamp: float
    score: float
    type: str  # "transcript" or "note"
    speaker_name: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response."""
    query: str
    mode: str
    results: List[SearchResult]
    total: int


async def search_meetings(
    db: AsyncSession,
    query: str,
    mode: str = "hybrid",
    limit: int = 20,
    meeting_id: Optional[UUID] = None
) -> SearchResponse:
    """
    Search across all meetings.
    
    Modes:
    - keyword: Full-text search with trigram similarity
    - semantic: Vector similarity search
    - hybrid: Combine both with RRF
    """
    
    if mode == "keyword":
        results = await _keyword_search(db, query, limit, meeting_id)
    elif mode == "semantic":
        results = await _semantic_search(db, query, limit, meeting_id)
    else:  # hybrid
        keyword_results = await _keyword_search(db, query, limit * 2, meeting_id)
        semantic_results = await _semantic_search(db, query, limit * 2, meeting_id)
        results = _reciprocal_rank_fusion(keyword_results, semantic_results, k=60)
        results = results[:limit]
    
    return SearchResponse(
        query=query,
        mode=mode,
        results=results,
        total=len(results)
    )


async def _keyword_search(
    db: AsyncSession,
    query: str,
    limit: int,
    meeting_id: Optional[UUID] = None
) -> List[SearchResult]:
    """Keyword search using trigram similarity."""
    
    # Search transcript segments
    segment_sql = """
        SELECT 
            s.id as segment_id,
            NULL::uuid as note_id,
            s.text,
            s.start_time as timestamp,
            similarity(s.text, :query) as score,
            s.meeting_id,
            m.title as meeting_title,
            sp.display_name as speaker_name,
            'transcript' as type
        FROM transcript_segments s
        JOIN meetings m ON s.meeting_id = m.id
        LEFT JOIN speakers sp ON s.speaker_id = sp.id
        WHERE s.text % :query
    """
    
    if meeting_id:
        segment_sql += " AND s.meeting_id = :meeting_id"
    
    segment_sql += " ORDER BY score DESC LIMIT :limit"
    
    # Search notes
    note_sql = """
        SELECT 
            NULL::uuid as segment_id,
            n.id as note_id,
            n.content as text,
            n.recording_offset as timestamp,
            similarity(n.content, :query) as score,
            n.meeting_id,
            m.title as meeting_title,
            NULL as speaker_name,
            'note' as type
        FROM notes n
        JOIN meetings m ON n.meeting_id = m.id
        WHERE n.content % :query
    """
    
    if meeting_id:
        note_sql += " AND n.meeting_id = :meeting_id"
    
    note_sql += " ORDER BY score DESC LIMIT :limit"
    
    params = {"query": query, "limit": limit}
    if meeting_id:
        params["meeting_id"] = meeting_id
    
    # Execute both queries
    segment_result = await db.execute(text(segment_sql), params)
    note_result = await db.execute(text(note_sql), params)
    
    results = []
    
    for row in segment_result:
        results.append(SearchResult(
            meeting_id=row.meeting_id,
            meeting_title=row.meeting_title,
            segment_id=row.segment_id,
            note_id=row.note_id,
            text=row.text,
            timestamp=row.timestamp,
            score=float(row.score),
            type=row.type,
            speaker_name=row.speaker_name
        ))
    
    for row in note_result:
        results.append(SearchResult(
            meeting_id=row.meeting_id,
            meeting_title=row.meeting_title,
            segment_id=row.segment_id,
            note_id=row.note_id,
            text=row.text,
            timestamp=row.timestamp,
            score=float(row.score),
            type=row.type,
            speaker_name=row.speaker_name
        ))
    
    # Sort by score and limit
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


async def _semantic_search(
    db: AsyncSession,
    query: str,
    limit: int,
    meeting_id: Optional[UUID] = None
) -> List[SearchResult]:
    """Semantic search using vector similarity."""
    
    # Generate query embedding
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    query_embedding = model.encode(query).tolist()
    
    # Search transcript segments with vectors
    segment_sql = """
        SELECT 
            s.id as segment_id,
            NULL::uuid as note_id,
            s.text,
            s.start_time as timestamp,
            1 - (s.embedding <=> :embedding) as score,
            s.meeting_id,
            m.title as meeting_title,
            sp.display_name as speaker_name,
            'transcript' as type
        FROM transcript_segments s
        JOIN meetings m ON s.meeting_id = m.id
        LEFT JOIN speakers sp ON s.speaker_id = sp.id
        WHERE s.embedding IS NOT NULL
    """
    
    if meeting_id:
        segment_sql += " AND s.meeting_id = :meeting_id"
    
    segment_sql += " ORDER BY s.embedding <=> :embedding LIMIT :limit"
    
    # Search notes with vectors
    note_sql = """
        SELECT 
            NULL::uuid as segment_id,
            n.id as note_id,
            n.content as text,
            n.recording_offset as timestamp,
            1 - (n.embedding <=> :embedding) as score,
            n.meeting_id,
            m.title as meeting_title,
            NULL as speaker_name,
            'note' as type
        FROM notes n
        JOIN meetings m ON n.meeting_id = m.id
        WHERE n.embedding IS NOT NULL
    """
    
    if meeting_id:
        note_sql += " AND n.meeting_id = :meeting_id"
    
    note_sql += " ORDER BY n.embedding <=> :embedding LIMIT :limit"
    
    params = {"embedding": str(query_embedding), "limit": limit}
    if meeting_id:
        params["meeting_id"] = meeting_id
    
    # Execute queries
    segment_result = await db.execute(text(segment_sql), params)
    note_result = await db.execute(text(note_sql), params)
    
    results = []
    
    for row in segment_result:
        results.append(SearchResult(
            meeting_id=row.meeting_id,
            meeting_title=row.meeting_title,
            segment_id=row.segment_id,
            note_id=row.note_id,
            text=row.text,
            timestamp=row.timestamp,
            score=float(row.score),
            type=row.type,
            speaker_name=row.speaker_name
        ))
    
    for row in note_result:
        results.append(SearchResult(
            meeting_id=row.meeting_id,
            meeting_title=row.meeting_title,
            segment_id=row.segment_id,
            note_id=row.note_id,
            text=row.text,
            timestamp=row.timestamp,
            score=float(row.score),
            type=row.type,
            speaker_name=row.speaker_name
        ))
    
    # Sort by score and limit
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


def _reciprocal_rank_fusion(
    keyword_results: List[SearchResult],
    semantic_results: List[SearchResult],
    k: int = 60
) -> List[SearchResult]:
    """
    Merge keyword and semantic results using Reciprocal Rank Fusion.
    
    RRF formula: score = sum(1 / (k + rank)) for each list
    """
    # Create dictionaries for O(1) lookup
    keyword_dict = {r.segment_id or r.note_id: (i, r) for i, r in enumerate(keyword_results)}
    semantic_dict = {r.segment_id or r.note_id: (i, r) for i, r in enumerate(semantic_results)}
    
    # Get all unique result IDs
    all_ids = set(keyword_dict.keys()) | set(semantic_dict.keys())
    
    # Calculate RRF scores
    rrf_scores = []
    for result_id in all_ids:
        score = 0.0
        
        if result_id in keyword_dict:
            rank = keyword_dict[result_id][0]
            score += 1.0 / (k + rank + 1)  # +1 because ranks are 0-indexed
        
        if result_id in semantic_dict:
            rank = semantic_dict[result_id][0]
            score += 1.0 / (k + rank + 1)
        
        # Use the result with the highest individual score
        if result_id in keyword_dict and result_id in semantic_dict:
            result = keyword_dict[result_id][1] if keyword_dict[result_id][1].score > semantic_dict[result_id][1].score else semantic_dict[result_id][1]
        elif result_id in keyword_dict:
            result = keyword_dict[result_id][1]
        else:
            result = semantic_dict[result_id][1]
        
        result.score = score
        rrf_scores.append((score, result))
    
    # Sort by RRF score
    rrf_scores.sort(key=lambda x: x[0], reverse=True)
    
    return [r for _, r in rrf_scores]
