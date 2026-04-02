"""NVIDIA embedding provider with local fallback."""

import logging

from fourdpocket.config import get_settings

logger = logging.getLogger(__name__)


class NvidiaEmbeddingProvider:
    """Embedding provider using NVIDIA API, falls back to local model."""

    def __init__(self):
        settings = get_settings()
        self._api_key = settings.ai.nvidia_api_key
        self._use_nvidia = bool(self._api_key) and settings.ai.embedding_provider == "nvidia"

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        if self._use_nvidia:
            try:
                return self._embed_nvidia(texts)
            except Exception as e:
                logger.warning("NVIDIA embedding failed, falling back to local: %s", e)

        return self._embed_local(texts)

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        results = self.embed([text])
        return results[0] if results else []

    def _embed_nvidia(self, texts: list[str]) -> list[list[float]]:
        """Use NVIDIA API for embeddings."""
        from openai import OpenAI

        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=self._api_key,
        )

        # NVIDIA supports batch embedding via OpenAI-compatible endpoint
        response = client.embeddings.create(
            model="nvidia/nv-embed-v1",
            input=texts,
            encoding_format="float",
        )

        return [item.embedding for item in response.data]

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Use local sentence-transformers as fallback."""
        from fourdpocket.ai.local_embeddings import get_local_embedder

        embedder = get_local_embedder()
        return embedder.embed(texts)
