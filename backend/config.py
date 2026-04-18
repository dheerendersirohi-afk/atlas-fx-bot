from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return default if raw is None else float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return default if raw is None else int(raw)


@dataclass(slots=True)
class AIProviderConfig:
    enabled: bool
    api_key: str
    model: str
    base_url: str
    available_models: tuple[str, ...] = ()


@dataclass(slots=True)
class BackendConfig:
    host: str
    port: int
    credentials_path: str
    state_file: str
    default_brain: str
    manual_approval: bool
    openai: AIProviderConfig
    gemini: AIProviderConfig
    sarvam: AIProviderConfig


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    return values or default


def load_backend_config(env_path: str | Path = "backend/.env") -> BackendConfig:
    _load_dotenv(Path(env_path))
    return BackendConfig(
        host=os.getenv("ATLAS_BACKEND_HOST", "127.0.0.1"),
        port=_env_int("ATLAS_BACKEND_PORT", 8787),
        credentials_path=os.getenv("ATLAS_CREDENTIALS_PATH", "config.live-connectors.example.json"),
        state_file=os.getenv("ATLAS_STATE_FILE", "backend/state.json"),
        default_brain=os.getenv("ATLAS_DEFAULT_BRAIN", "rules"),
        manual_approval=_env_bool("ATLAS_MANUAL_APPROVAL", True),
        openai=AIProviderConfig(
            enabled=_env_bool("OPENAI_ENABLED", False),
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1/responses"),
        ),
        gemini=AIProviderConfig(
            enabled=_env_bool("GEMINI_ENABLED", False),
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            base_url=os.getenv(
                "GEMINI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            ),
        ),
        sarvam=AIProviderConfig(
            enabled=_env_bool("SARVAM_ENABLED", False),
            api_key=os.getenv("SARVAM_API_KEY", ""),
            model=os.getenv("SARVAM_MODEL", "sarvam-30b"),
            base_url=os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai/v1/chat/completions"),
            available_models=_env_csv("SARVAM_AVAILABLE_MODELS", ("sarvam-30b", "sarvam-105b", "sarvam-m")),
        ),
    )
