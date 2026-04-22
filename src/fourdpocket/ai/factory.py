"""AI provider factory - creates providers from configuration."""

import logging

from fourdpocket.ai.base import NoOpChatProvider
from fourdpocket.config import get_settings

logger = logging.getLogger(__name__)


def get_ai_overrides_from_db() -> dict:
    """Read admin AI config overrides from InstanceSettings.extra['ai_config'].

    Returns empty dict if no overrides are set or DB is not available.
    """
    try:
        from sqlmodel import Session

        from fourdpocket.db.session import get_engine
        from fourdpocket.models.instance_settings import InstanceSettings

        engine = get_engine()
        with Session(engine) as db:
            settings = db.get(InstanceSettings, 1)
            if settings and settings.extra:
                return settings.extra.get("ai_config", {})
    except Exception as e:
        logger.debug("Could not read AI overrides from DB: %s", e)
    return {}


def get_resolved_ai_config() -> dict:
    """Return merged AI config: env defaults + admin DB overrides.

    Admin DB overrides take precedence over env vars.
    """
    settings = get_settings()
    base = {
        "chat_provider": settings.ai.chat_provider,
        "ollama_url": settings.ai.ollama_url,
        "ollama_model": settings.ai.ollama_model,
        "groq_api_key": settings.ai.groq_api_key,
        "nvidia_api_key": settings.ai.nvidia_api_key,
        "custom_base_url": settings.ai.custom_base_url,
        "custom_api_key": settings.ai.custom_api_key,
        "custom_model": settings.ai.custom_model,
        "custom_api_type": settings.ai.custom_api_type,
        "embedding_provider": settings.ai.embedding_provider,
        "embedding_model": settings.ai.embedding_model,
        "auto_tag": settings.ai.auto_tag,
        "auto_summarize": settings.ai.auto_summarize,
        "tag_confidence_threshold": settings.ai.tag_confidence_threshold,
        "tag_suggestion_threshold": settings.ai.tag_suggestion_threshold,
        "sync_enrichment": settings.ai.sync_enrichment,
    }
    # Merge DB overrides (admin panel takes precedence)
    overrides = get_ai_overrides_from_db()
    for key, value in overrides.items():
        if key in base and value not in (None, ""):
            base[key] = value
    return base


def get_chat_provider(overrides: dict | None = None):
    """Return the configured chat provider.

    Args:
        overrides: Optional dict to override settings (used when admin config is pre-loaded).
                   If None, reads from env + DB automatically.
    """
    if overrides is None:
        overrides = get_ai_overrides_from_db()

    settings = get_settings()
    provider_name = overrides.get("chat_provider") or settings.ai.chat_provider

    _valid_providers = {"ollama", "groq", "nvidia", "custom", "noop"}
    if isinstance(provider_name, str) and provider_name and provider_name not in _valid_providers:
        raise ValueError(
            f"Unknown chat provider {provider_name!r}. "
            f"Must be one of: {sorted(_valid_providers)}"
        )

    if provider_name in ("ollama", "groq", "nvidia", "custom"):
        try:
            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            return OpenAICompatibleProvider(provider_name, overrides=overrides)
        except Exception as e:
            logger.warning("Failed to create %s provider: %s", provider_name, e)
            return NoOpChatProvider()

    logger.info("AI chat disabled, using NoOpChatProvider")
    return NoOpChatProvider()


def get_embedding_provider():
    """Return the configured embedding provider."""
    settings = get_settings()
    overrides = get_ai_overrides_from_db()
    embedding_provider = overrides.get("embedding_provider") or settings.ai.embedding_provider
    nvidia_key = overrides.get("nvidia_api_key") or settings.ai.nvidia_api_key

    if embedding_provider == "nvidia" and nvidia_key:
        try:
            from fourdpocket.ai.nvidia_embeddings import NvidiaEmbeddingProvider
            return NvidiaEmbeddingProvider()
        except Exception as e:
            logger.warning("Failed to create NVIDIA embedding provider: %s", e)

    # Default to local
    from fourdpocket.ai.local_embeddings import get_local_embedder
    return get_local_embedder()
