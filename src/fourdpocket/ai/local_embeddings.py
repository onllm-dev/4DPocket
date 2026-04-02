"""Local embedding using sentence-transformers."""

import logging
from concurrent.futures import ThreadPoolExecutor

from fourdpocket.config import get_settings

logger = logging.getLogger(__name__)

_model = None
_executor = ThreadPoolExecutor(max_workers=1)


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        model_name = settings.ai.embedding_model
        logger.info("Loading embedding model: %s", model_name)
        _model = SentenceTransformer(model_name)
    return _model


class LocalEmbeddingProvider:
    """Embedding provider using local sentence-transformers."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local model."""
        model = _load_model()
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        results = self.embed([text])
        return results[0] if results else []


_instance = None


def get_local_embedder() -> LocalEmbeddingProvider:
    global _instance
    if _instance is None:
        _instance = LocalEmbeddingProvider()
    return _instance
