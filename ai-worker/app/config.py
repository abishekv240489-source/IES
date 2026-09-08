from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    mapping_provider: str = os.getenv("IES_MAPPING_PROVIDER", "hybrid").lower()
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M")
    request_timeout_seconds: float = float(os.getenv("IES_LLM_TIMEOUT_SECONDS", "300"))
    hybrid_fast_path: bool = _bool("IES_HYBRID_FAST_PATH", False)
    hybrid_min_populated_fields: int = int(os.getenv("IES_HYBRID_MIN_POPULATED_FIELDS", "18"))
    max_pages: int = int(os.getenv("IES_MAX_PAGES", "20"))
    max_file_bytes: int = int(os.getenv("IES_MAX_FILE_BYTES", str(20 * 1024 * 1024)))
    embedded_text_min_chars: int = int(os.getenv("IES_EMBEDDED_TEXT_MIN_CHARS", "120"))
    demo_fallback: bool = _bool("IES_AI_DEMO_FALLBACK", True)
    paddle_required: bool = _bool("IES_PADDLEOCR_REQUIRED", True)
    paddle_language: str = os.getenv("PADDLEOCR_LANG", "en")
    paddle_enable_mkldnn: bool = _bool("PADDLEOCR_ENABLE_MKLDNN", True)
    paddle_detection_model: str = os.getenv("PADDLEOCR_DETECTION_MODEL", "PP-OCRv5_mobile_det")
    paddle_recognition_model: str = os.getenv("PADDLEOCR_RECOGNITION_MODEL", "en_PP-OCRv5_mobile_rec")
    paddle_recognition_batch_size: int = int(os.getenv("PADDLEOCR_RECOGNITION_BATCH_SIZE", "16"))
    paddle_detection_limit_side: int = int(os.getenv("PADDLEOCR_DETECTION_LIMIT_SIDE", "1280"))
    paddle_detection_limit_type: str = os.getenv("PADDLEOCR_DETECTION_LIMIT_TYPE", "max")
    paddle_use_orientation: bool = _bool("PADDLEOCR_USE_ORIENTATION", False)
    paddle_use_unwarping: bool = _bool("PADDLEOCR_USE_UNWARPING", False)
    paddle_use_textline_orientation: bool = _bool("PADDLEOCR_USE_TEXTLINE_ORIENTATION", False)


settings = Settings()
