from app.core.sessions import get_session_factory, get_db as _get_db, Base

AsyncSessionLocal = get_session_factory()


async def get_db():
    """FastAPI dependency for database sessions."""
    async for session in _get_db():
        yield session
