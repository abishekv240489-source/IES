from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="IES_", extra="ignore")

    env: str = "development"
    log_level: str = "INFO"
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_pages: int = Field(default=20, gt=0, le=500)
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    ollama_timeout_seconds: float = Field(default=45, gt=0, le=300)
    data_dir: Path = Path("data")


@lru_cache
def get_settings() -> Settings:
    return Settings()
