import os
from typing import List
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    DATABASE_URL: str = (
        "postgresql+asyncpg://meetscribe:Birdsey5%40@localhost:5433/meetscribe"
    )
    REDIS_URL: str = "redis://localhost:6381/0"

    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 2
    AUDIO_CHUNK_SECONDS: int = 30
    RECORDINGS_PATH: str = "/data/recordings"
    AUDIO_DAEMON_SOCKET: str = "/tmp/meetscribe-audio.sock"
    AUDIO_DAEMON_HOST: str = "localhost"
    AUDIO_DAEMON_PORT: int = 9000

    WHISPER_MODEL: str = "medium"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_BATCH_SIZE: int = 8
    HF_TOKEN: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # OpenRouter (optional alternative to local Ollama)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"

    # LLM provider for summarization: "ollama" or "openrouter"
    LLM_PROVIDER: str = "ollama"

    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    OUTLOOK_CLIENT_ID: Optional[str] = None
    OUTLOOK_CLIENT_SECRET: Optional[str] = None
    CALENDAR_SYNC_INTERVAL_MINUTES: int = 5

    ENCRYPTION_KEY: Optional[str] = None
    SECRET_KEY: str = "change-me-in-production"

    API_V1_PREFIX: str = "/api/v1"

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


def get_cors_origins() -> List[str]:
    """Parse CORS origins from comma-separated string."""
    origins = settings.CORS_ORIGINS
    if not origins:
        return []
    return [origin.strip() for origin in origins.split(",")]
