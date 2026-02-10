from fastapi import APIRouter
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    # Check database connection
    try:
        async with AsyncSessionLocal() as session:
            # Simple connection test - just execute and check for exception
            await session.execute(text("SELECT 1"))
            await session.commit()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "service": "meetscribe-api"
    }
