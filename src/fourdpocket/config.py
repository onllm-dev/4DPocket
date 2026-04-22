"""Application configuration via pydantic-settings."""

import secrets

# Load .env file into os.environ so nested settings classes pick up the values.
# Skip during pytest to avoid .env values interfering with test expectations.
import sys as _sys
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if "pytest" not in _sys.modules:
    try:
        from dotenv import load_dotenv
        load_dotenv(override=False)
    except ImportError:
        pass


def _get_or_create_secret_key() -> str:
    """Get secret key from env, file, or generate and persist one.

    Uses file locking to prevent TOCTOU race conditions when multiple
    processes start simultaneously.
    """
    import fcntl
    import os

    env_key = os.environ.get("FDP_AUTH__SECRET_KEY")
    if env_key:
        return env_key
    key_dir = Path.home() / ".4dpocket"
    key_dir.mkdir(parents=True, exist_ok=True)
    key_file = key_dir / "secret_key"
    lock_file = key_dir / "secret_key.lock"
    with open(lock_file, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if key_file.exists():
                return key_file.read_text().strip()
            key = secrets.token_urlsafe(32)
            key_file.write_text(key)
            key_file.chmod(0o600)  # Owner read/write only
            return key
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_DATABASE__")

    url: str = "sqlite:///./data/4dpocket.db"
    echo: bool = False


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_AUTH__")

    secret_key: str = Field(default_factory=_get_or_create_secret_key)
    algorithm: str = "HS256"  # Hardcoded in auth_utils — do not change
    token_expire_minutes: int = 10080  # 7 days
    mode: str = "single"  # "single" or "multi"


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_STORAGE__")

    base_path: str = "./data"
    max_archive_size_mb: int = 50


class SearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_SEARCH__")

    backend: str = "sqlite"  # "sqlite" or "meilisearch"
    meili_url: str = "http://localhost:7700"
    meili_master_key: str = ""
    vector_backend: str = "auto"  # "auto", "chroma", "pgvector"
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    max_chunks_per_item: int = 200
    # Graph-anchored ranker — third RRF input sourced from the concept graph.
    # Default-on: no-op for users without entity data, contributes when entities
    # have been populated by the enrichment pipeline. Admins can disable from
    # the admin panel (InstanceSettings.extra["search_config"]).
    graph_ranker_enabled: bool = True
    graph_ranker_hop_decay: float = 0.5  # neighbor contribution = weight * hop_decay
    graph_ranker_top_k: int = 50  # max items returned by the graph ranker


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_AI__")

    chat_provider: str = "ollama"  # "ollama", "groq", "nvidia", "custom"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    groq_api_key: str = ""
    nvidia_api_key: str = ""
    # Custom provider (any OpenAI-compatible or Anthropic-compatible endpoint)
    custom_base_url: str = ""
    custom_api_key: str = ""
    custom_model: str = ""
    custom_api_type: str = "openai"  # "openai" or "anthropic"
    embedding_provider: str = "local"  # "local" or "nvidia"
    embedding_model: str = "all-MiniLM-L6-v2"
    auto_tag: bool = True
    auto_summarize: bool = True
    tag_confidence_threshold: float = 0.7
    tag_suggestion_threshold: float = 0.4
    sync_enrichment: bool = False  # Set True in .env to run AI inline if Huey not running


class RerankSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_RERANK__")

    enabled: bool = False
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    candidate_pool: int = 50
    top_k: int = 20


class EnrichmentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_ENRICHMENT__")

    extract_entities: bool = False
    max_entities_per_chunk: int = 20
    max_relations_per_chunk: int = 15
    max_attempts: int = 5  # Max retries per enrichment stage before permanent failure
    # Entity synthesis — Karpathy-style LLM-maintained wiki pages per entity.
    synthesis_enabled: bool = True
    synthesis_min_item_count: int = 3  # Don't synthesize entities mentioned in < N items
    synthesis_threshold: int = 3  # Regen when item_count - synthesis_item_count >= N
    synthesis_min_interval_hours: int = 24  # No more than once per entity per interval
    synthesis_max_context_items: int = 20  # Cap evidence fed to the LLM per regen


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_SERVER__")

    host: str = "0.0.0.0"
    port: int = 4040
    public_url: str = "http://localhost:4040"  # Canonical public URL (used by MCP issuer/resource)
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4040"]
    secure_cookies: bool = False  # Set True behind HTTPS in production
    trust_proxy: bool = False  # Set True when behind a reverse proxy (nginx, caddy, etc.)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FDP_")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    ai: AISettings = Field(default_factory=AISettings)
    rerank: RerankSettings = Field(default_factory=RerankSettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)

    @model_validator(mode="after")
    def validate_search_db_compat(self) -> "Settings":
        if not self.database.url.startswith("sqlite") and self.search.backend == "sqlite":
            import logging
            logging.getLogger(__name__).warning(
                "FDP_SEARCH__BACKEND=sqlite is incompatible with PostgreSQL. "
                "Auto-switching to 'meilisearch'. Set FDP_SEARCH__BACKEND=meilisearch explicitly."
            )
            self.search.backend = "meilisearch"
        return self


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
