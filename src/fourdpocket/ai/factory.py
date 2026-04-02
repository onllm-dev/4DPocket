"""AI provider factory - creates providers from configuration."""

import logging

from fourdpocket.ai.base import NoOpChatProvider
from fourdpocket.config import get_settings

logger = logging.getLogger(__name__)


def get_chat_provider():
    """Return the configured chat provider."""
    settings = get_settings()
    provider_name = settings.ai.chat_provider

    if provider_name in ("ollama", "groq", "nvidia"):
        try:
            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            return OpenAICompatibleProvider(provider_name)
        except Exception as e:
            logger.warning("Failed to create %s provider: %s", provider_name, e)
            return NoOpChatProvider()

    logger.info("AI chat disabled, using NoOpChatProvider")
    return NoOpChatProvider()


def get_embedding_provider():
    """Return the configured embedding provider."""
    settings = get_settings()

    if settings.ai.embedding_provider == "nvidia" and settings.ai.nvidia_api_key:
        try:
            from fourdpocket.ai.nvidia_embeddings import NvidiaEmbeddingProvider
            return NvidiaEmbeddingProvider()
        except Exception as e:
            logger.warning("Failed to create NVIDIA embedding provider: %s", e)

    # Default to local
    from fourdpocket.ai.local_embeddings import get_local_embedder
    return get_local_embedder()
