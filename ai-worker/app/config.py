from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mapping_provider: str = os.getenv("IES_MAPPING_PROVIDER", "ollama").lower()
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
    request_timeout_seconds: float = float(os.getenv("IES_LLM_TIMEOUT_SECONDS", "10"))
    max_pages: int = int(os.getenv("IES_MAX_PAGES", "20"))
    max_file_bytes: int = int(os.getenv("IES_MAX_FILE_BYTES", str(20 * 1024 * 1024)))
    embedded_text_min_chars: int = int(os.getenv("IES_EMBEDDED_TEXT_MIN_CHARS", "120"))
    demo_fallback: bool = _bool("IES_AI_DEMO_FALLBACK", True)
    paddle_language: str = os.getenv("PADDLEOCR_LANG", "en")


settings = Settings()
