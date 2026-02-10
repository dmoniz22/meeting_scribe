from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.services.search import search_meetings, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    mode: str = Field(default="hybrid", pattern="^(keyword|semantic|hybrid)$")
    limit: int = Field(default=20, ge=1, le=100)


@router.post("", response_model=SearchResponse)
async def search_endpoint(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Search across all meetings.
    
    Modes:
    - **keyword**: Full-text search using PostgreSQL trigram similarity
    - **semantic**: Vector similarity search using pgvector
    - **hybrid**: Combines both with Reciprocal Rank Fusion (default)
    
    Results include transcript segments and notes, ranked by relevance.
    """
    try:
        results = await search_meetings(
            db=db,
            query=request.query,
            mode=request.mode,
            limit=request.limit
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
