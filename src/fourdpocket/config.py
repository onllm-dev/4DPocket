"""Application configuration via pydantic-settings."""

import secrets
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_or_create_secret_key() -> str:
    """Get secret key from env, file, or generate and persist one."""
    import os

    env_key = os.environ.get("FDP_AUTH__SECRET_KEY")
    if env_key:
        return env_key
    key_file = Path.home() / ".4dpocket" / "secret_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(32)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(key)
    key_file.chmod(0o600)  # Owner read/write only
    return key


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_DATABASE__")

    url: str = "sqlite:///./data/4dpocket.db"
    echo: bool = False


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_AUTH__")

    secret_key: str = Field(default_factory=_get_or_create_secret_key)
    algorithm: str = "HS256"
    token_expire_minutes: int = 10080  # 7 days
    mode: str = "single"  # "single" or "multi"


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_STORAGE__")

    base_path: str = "./data"
    max_archive_size_mb: int = 50
    screenshot_quality: int = 80


class SearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_SEARCH__")

    backend: str = "sqlite"  # "sqlite" or "meilisearch"
    meili_url: str = "http://localhost:7700"
    meili_master_key: str = ""


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_AI__")

    chat_provider: str = "ollama"  # "ollama", "groq", "nvidia"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    groq_api_key: str = ""
    nvidia_api_key: str = ""
    embedding_provider: str = "local"  # "local" or "nvidia"
    embedding_model: str = "all-MiniLM-L6-v2"
    auto_tag: bool = True
    auto_summarize: bool = True
    tag_confidence_threshold: float = 0.7
    tag_suggestion_threshold: float = 0.4


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_SERVER__")

    host: str = "0.0.0.0"
    port: int = 4040
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4040"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    ai: AISettings = Field(default_factory=AISettings)
    server: ServerSettings = Field(default_factory=ServerSettings)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
