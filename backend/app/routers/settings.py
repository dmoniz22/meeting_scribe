from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List
from app.core.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])


class ModelInfo(BaseModel):
    id: str
    name: str
    description: str
    size: str | None = None


class ModelSettings(BaseModel):
    whisper_model: str = "medium"
    whisper_compute_type: str = "float16"
    ollama_model: str = "llama3.1:8b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


WHISPER_MODELS = [
    ModelInfo(id="tiny", name="Tiny", description="Fastest, lowest accuracy", size="39 MB"),
    ModelInfo(id="base", name="Base", description="Fast, good for real-time", size="74 MB"),
    ModelInfo(id="small", name="Small", description="Balanced speed/accuracy", size="244 MB"),
    ModelInfo(id="medium", name="Medium", description="High accuracy", size="769 MB"),
    ModelInfo(id="large-v3", name="Large v3", description="Best accuracy, slowest", size="1.5 GB"),
]

OLLAMA_MODELS = [
    ModelInfo(id="llama3.1:8b", name="Llama 3.1 (8B)", description="Fast, good quality", size="4.7 GB"),
    ModelInfo(id="llama3.1:70b", name="Llama 3.1 (70B)", description="Best quality, slow", size="40 GB"),
    ModelInfo(id="mistral:7b", name="Mistral (7B)", description="Fast, efficient", size="4.1 GB"),
    ModelInfo(id="mixtral:8x7b", name="Mixtral (8x7B)", description="High quality", size="26 GB"),
]


@router.get("/models")
async def get_available_models():
    """Get list of available models."""
    return {
        "transcription_models": [m.model_dump() for m in WHISPER_MODELS],
        "summarization_models": [m.model_dump() for m in OLLAMA_MODELS],
    }


@router.get("/models/current", response_model=ModelSettings)
async def get_current_settings():
    """Get current model settings."""
    return ModelSettings(
        whisper_model=settings.WHISPER_MODEL,
        whisper_compute_type=settings.WHISPER_COMPUTE_TYPE,
        ollama_model=settings.OLLAMA_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
    )


@router.put("/models", response_model=ModelSettings)
async def update_settings(model_settings: ModelSettings):
    """Update model settings."""
    settings.WHISPER_MODEL = model_settings.whisper_model
    settings.WHISPER_COMPUTE_TYPE = model_settings.whisper_compute_type
    settings.OLLAMA_MODEL = model_settings.ollama_model
    settings.EMBEDDING_MODEL = model_settings.embedding_model
    return model_settings
