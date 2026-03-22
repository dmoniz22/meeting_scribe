import os
from typing import List, Optional, Dict, Any

from fastapi import APIRouter
from pydantic import BaseModel
import httpx

from app.core.config import settings

router = APIRouter(prefix="/settings", tags=["settings"])

WHISPER_MODEL_SIZES = {
    "tiny": "39 MB",
    "base": "74 MB",
    "small": "244 MB",
    "medium": "769 MB",
    "large-v3": "1.5 GB",
    "large": "1.5 GB",
}


def _check_hf_cache(model_pattern: str) -> bool:
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    if not os.path.isdir(cache_dir):
        return False
    for entry in os.listdir(cache_dir):
        if model_pattern in entry.replace("--", "/"):
            full = os.path.join(cache_dir, entry)
            snapshots = os.path.join(full, "snapshots")
            if os.path.isdir(snapshots):
                for snap in os.listdir(snapshots):
                    snap_dir = os.path.join(snapshots, snap)
                    if os.listdir(snap_dir):
                        return True
    return False


def _format_size(bytes_val: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.0f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} TB"


def _check_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _check_ollama() -> bool:
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _get_env_values() -> dict:
    """Read current values from the .env file."""
    env_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    env_file = os.path.join(env_dir, ".env")
    values = {}
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    values[key.strip()] = val.strip()
    return values


def _get_ollama_models() -> List[Dict[str, Any]]:
    try:
        resp = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "id": m["name"],
                "label": m["name"],
                "size": _format_size(m.get("size", 0)),
                "downloaded": True,
                "source": "ollama",
            }
            for m in data.get("models", [])
        ]
    except Exception:
        return []


# --- Models ---


class ModelInfo(BaseModel):
    id: str
    label: str
    size: str = ""
    downloaded: bool = False
    source: str = ""


class ModelSettings(BaseModel):
    whisper_model: str = "medium"
    whisper_compute_type: str = "float16"
    whisper_batch_size: int = 8
    ollama_model: str = "llama3.1:8b"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_provider: str = "ollama"
    openrouter_model: str = "openai/gpt-4o-mini"


class SettingsResponse(BaseModel):
    whisper_models: List[ModelInfo]
    ollama_models: List[ModelInfo]
    embedding_models: List[ModelInfo]
    openrouter_models: List[ModelInfo]
    current: ModelSettings
    dependencies: Dict[str, bool]


@router.get("", response_model=SettingsResponse)
async def get_settings():
    whisper_models = [
        ModelInfo(
            id=n,
            label=n.title(),
            size=WHISPER_MODEL_SIZES.get(n, "?"),
            downloaded=_check_hf_cache(f"faster-whisper-{n}"),
            source="huggingface",
        )
        for n in ["tiny", "base", "small", "medium", "large-v3"]
    ]

    ollama_models = [ModelInfo(**m) for m in _get_ollama_models()]

    embedding_models = [
        ModelInfo(
            id="sentence-transformers/all-MiniLM-L6-v2",
            label="MiniLM L6 (fast)",
            size="80 MB",
            downloaded=_check_hf_cache("all-MiniLM-L6-v2"),
            source="huggingface",
        ),
        ModelInfo(
            id="sentence-transformers/all-mpnet-base-v2",
            label="MPNet Base (accurate)",
            size="420 MB",
            downloaded=_check_hf_cache("all-mpnet-base-v2"),
            source="huggingface",
        ),
    ]

    openrouter_models = [
        ModelInfo(
            id="openai/gpt-4o-mini",
            label="GPT-4o Mini (fast, cheap)",
            source="openrouter",
        ),
        ModelInfo(
            id="openai/gpt-4o", label="GPT-4o (best quality)", source="openrouter"
        ),
        ModelInfo(
            id="anthropic/claude-3.5-sonnet",
            label="Claude 3.5 Sonnet",
            source="openrouter",
        ),
        ModelInfo(
            id="google/gemini-pro-1.5", label="Gemini Pro 1.5", source="openrouter"
        ),
        ModelInfo(
            id="meta-llama/llama-3.1-405b-instruct",
            label="Llama 3.1 405B",
            source="openrouter",
        ),
    ]

    deps = {
        "whisperx": _check_module("whisperx"),
        "pyannote": _check_module("pyannote.audio"),
        "sentence_transformers": _check_module("sentence_transformers"),
        "torch": _check_module("torch"),
        "hf_token": bool(settings.HF_TOKEN),
        "ollama_reachable": _check_ollama(),
        "openrouter_key": bool(settings.OPENROUTER_API_KEY),
    }

    env = _get_env_values()
    current = ModelSettings(
        whisper_model=env.get("WHISPER_MODEL", settings.WHISPER_MODEL),
        whisper_compute_type=env.get(
            "WHISPER_COMPUTE_TYPE", settings.WHISPER_COMPUTE_TYPE
        ),
        whisper_batch_size=int(
            env.get("WHISPER_BATCH_SIZE", settings.WHISPER_BATCH_SIZE)
        ),
        ollama_model=env.get("OLLAMA_MODEL", settings.OLLAMA_MODEL),
        embedding_model=env.get("EMBEDDING_MODEL", settings.EMBEDDING_MODEL),
        llm_provider=env.get("LLM_PROVIDER", settings.LLM_PROVIDER),
        openrouter_model=env.get("OPENROUTER_MODEL", settings.OPENROUTER_MODEL),
    )

    return SettingsResponse(
        whisper_models=whisper_models,
        ollama_models=ollama_models,
        embedding_models=embedding_models,
        openrouter_models=openrouter_models,
        current=current,
        dependencies=deps,
    )


class SettingsUpdate(BaseModel):
    whisper_model: Optional[str] = None
    whisper_compute_type: Optional[str] = None
    whisper_batch_size: Optional[int] = None
    ollama_model: Optional[str] = None
    embedding_model: Optional[str] = None
    llm_provider: Optional[str] = None
    openrouter_model: Optional[str] = None
    hf_token: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    ollama_base_url: Optional[str] = None


@router.post("", response_model=SettingsResponse)
async def update_settings(request: SettingsUpdate):
    updates = {}
    for field, value in request.model_dump(exclude_unset=True).items():
        if value is not None:
            updates[field.upper()] = value

    # Write to .env file
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    env_file = os.path.join(backend_dir, ".env")

    current_env = {}
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    current_env[key.strip()] = val.strip()

    for key, value in updates.items():
        current_env[key] = str(value)

    with open(env_file, "w") as f:
        for key, value in current_env.items():
            f.write(f"{key}={value}\n")

    return await get_settings()
