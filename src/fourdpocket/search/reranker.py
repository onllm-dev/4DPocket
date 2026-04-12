"""Reranker implementations — optional cross-encoder stage after RRF fusion."""

import logging

logger = logging.getLogger(__name__)


class NullReranker:
    """Pass-through — no reranking, returns indices in original order."""

    def rerank(
        self, query: str, docs: list[str], top_k: int
    ) -> list[tuple[int, float]]:
        return [(i, 1.0) for i in range(min(top_k, len(docs)))]


class LocalReranker:
    """Cross-encoder reranking via sentence-transformers CrossEncoder."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model_name = model_name
        self._model = None
        self._load_failed = False

    def _load(self):
        if self._model is not None or self._load_failed:
            return
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed — reranker disabled. "
                "Install with: pip install sentence-transformers"
            )
            self._load_failed = True
        except Exception as e:
            logger.warning("Failed to load reranker model %s: %s", self._model_name, e)
            self._load_failed = True

    def rerank(
        self, query: str, docs: list[str], top_k: int
    ) -> list[tuple[int, float]]:
        self._load()
        if self._model is None:
            # Return None to signal caller should skip reranking entirely
            return None

        if not docs:
            return []

        pairs = [(query, doc) for doc in docs]
        scores = self._model.predict(pairs)
        ranked = sorted(enumerate(scores), key=lambda x: -x[1])
        return [(int(idx), float(score)) for idx, score in ranked[:top_k]]


def build_reranker(settings=None):
    """Build the appropriate reranker from config."""
    if settings is None:
        from fourdpocket.config import get_settings

        settings = get_settings()

    rerank_cfg = getattr(settings, "rerank", None)
    if rerank_cfg is None or not getattr(rerank_cfg, "enabled", False):
        return NullReranker()

    model = getattr(rerank_cfg, "model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    return LocalReranker(model_name=model)
