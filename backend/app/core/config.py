import os
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://meetscribe:Birdsey5%40@localhost:5432/meetscribe"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Audio
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 2
    AUDIO_CHUNK_SECONDS: int = 30
    RECORDINGS_PATH: str = "/data/recordings"
    AUDIO_DAEMON_SOCKET: str = "/tmp/meetscribe-audio.sock"
    
    # AI/ML
    WHISPER_MODEL: str = "medium"
    WHISPER_COMPUTE_TYPE: str = "float16"
    WHISPER_BATCH_SIZE: int = 8
    HF_TOKEN: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Calendar
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    OUTLOOK_CLIENT_ID: Optional[str] = None
    OUTLOOK_CLIENT_SECRET: Optional[str] = None
    CALENDAR_SYNC_INTERVAL_MINUTES: int = 5
    
    # Security
    ENCRYPTION_KEY: Optional[str] = None
    SECRET_KEY: str = "change-me-in-production"
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
