from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.routers import meetings, health, recordings, search, websocket, meeting_detail, settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="MeetScribe API",
    description="Local-First Linux Meeting Assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(meetings.router, prefix="/api/v1")
app.include_router(recordings.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(websocket.router, prefix="/api/v1")
app.include_router(meeting_detail.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": "Welcome to MeetScribe API",
        "version": "1.0.0",
        "docs": "/docs"
    }
