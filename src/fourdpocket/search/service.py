"""SearchService — unified search orchestrator using pluggable backends."""

import logging
import uuid
from collections import defaultdict

from sqlmodel import Session

from fourdpocket.search.base import (
    GraphHit,
    KeywordBackend,
    KeywordHit,
    SearchFilters,
    SearchResult,
    VectorBackend,
)

logger = logging.getLogger(__name__)


class SearchService:
    """Orchestrates keyword + vector search with optional reranking."""

    def __init__(
        self,
        keyword: KeywordBackend,
        vector: VectorBackend,
        reranker=None,
    ):
        self._keyword = keyword
        self._vector = vector
        self._reranker = reranker

    def index_item(self, db: Session, item: object) -> None:
        """Index an item in the keyword backend."""
        try:
            self._keyword.index_item(db, item)
        except Exception as e:
            logger.warning("Keyword indexing failed: %s", e)

    def index_chunks(
        self,
        db: Session,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        chunks: list,
        title: str | None = None,
        url: str | None = None,
    ) -> None:
        """Index chunks in the keyword backend."""
        try:
            self._keyword.index_chunks(db, item_id, user_id, chunks, title, url)
        except Exception as e:
            logger.warning("Chunk keyword indexing failed: %s", e)

    def upsert_item_embedding(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> None:
        """Store an item-level embedding in the vector backend."""
        try:
            self._vector.upsert_item(item_id, user_id, embedding, metadata)
        except Exception as e:
            logger.warning("Item embedding upsert failed: %s", e)

    def upsert_chunk_embedding(
        self,
        chunk_id: uuid.UUID,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        embedding: list[float],
        metadata: dict | None = None,
    ) -> None:
        """Store a chunk-level embedding in the vector backend."""
        try:
            self._vector.upsert_chunk(chunk_id, item_id, user_id, embedding, metadata)
        except Exception as e:
            logger.warning("Chunk embedding upsert failed: %s", e)

    def delete_item(self, db: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Remove an item from all backends."""
        try:
            self._keyword.delete_item(db, item_id)
        except Exception as e:
            logger.warning("Keyword delete failed: %s", e)
        try:
            self._vector.delete_item(item_id, user_id)
        except Exception as e:
            logger.warning("Vector delete failed: %s", e)

    def search(
        self,
        db: Session,
        query: str,
        user_id: uuid.UUID,
        filters: SearchFilters | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SearchResult]:
        """Run hybrid search: keyword + vector + RRF fusion + optional rerank."""
        if filters is None:
            filters = SearchFilters()

        # Resolve collection-level ACL into a concrete item_id allow-set that all
        # backends can be post-filtered against.
        if filters.collection_id is not None:
            from sqlmodel import select as _select

            from fourdpocket.models.collection import CollectionItem

            col_items = db.exec(
                _select(CollectionItem.item_id).where(
                    CollectionItem.collection_id == filters.collection_id
                )
            ).all()
            coll_set = set(col_items)
            if filters.allowed_item_ids is None:
                filters.allowed_item_ids = coll_set
            else:
                filters.allowed_item_ids = filters.allowed_item_ids & coll_set

        # Fetch enough candidates to cover offset + limit after fusion. When an
        # ACL filter is active we over-fetch further since we'll be dropping hits.
        base_fetch = max((offset + limit) * 2, limit * 3)
        fetch_size = base_fetch * 3 if filters.allowed_item_ids is not None else base_fetch

        # 1. Keyword search
        keyword_hits = self._keyword.search(
            db, query, user_id, filters, limit=fetch_size, offset=0,
        )

        # 2. Vector search (embed query, then search)
        vector_hits = []
        if query.strip():
            try:
                from fourdpocket.ai.factory import get_embedding_provider

                provider = get_embedding_provider()
                query_embedding = provider.embed_single(query)
                if query_embedding:
                    vector_hits = self._vector.search(
                        user_id, query_embedding, k=fetch_size
                    )
            except Exception as e:
                logger.debug("Vector search unavailable: %s", e)

        # 2b. Graph-anchored ranker (third RRF input).
        # Default-on at env level; admin can disable via InstanceSettings.
        # No-op silently if entity data has not been populated yet.
        graph_hits: list[GraphHit] = []
        try:
            from fourdpocket.search.admin_config import get_resolved_search_config

            search_cfg = get_resolved_search_config()
            if search_cfg.get("graph_ranker_enabled", True):
                from fourdpocket.search.graph_ranker import graph_anchored_hits

                graph_hits = graph_anchored_hits(
                    db,
                    query,
                    user_id,
                    k=int(search_cfg.get("graph_ranker_top_k", 50)),
                    hop_decay=float(search_cfg.get("graph_ranker_hop_decay", 0.5)),
                )
        except Exception as e:
            logger.debug("Graph ranker unavailable: %s", e)

        # 3. RRF fusion (N rankers)
        merged = self._rrf_fusion_n([
            ("fts", keyword_hits),
            ("semantic", vector_hits),
            ("graph", graph_hits),
        ], k=max(fetch_size, 60))

        # 3b. Apply collection-level ACL by intersecting with the allow-set.
        if filters.allowed_item_ids is not None:
            allowed_str = {str(i) for i in filters.allowed_item_ids}
            merged = [r for r in merged if str(r.item_id) in allowed_str]

        if not merged:
            return []

        # 4. Optional reranking
        if self._reranker is not None and hasattr(self._reranker, "rerank"):
            from fourdpocket.config import get_settings

            settings = get_settings()
            rerank_cfg = getattr(settings, "rerank", None)
            if rerank_cfg and getattr(rerank_cfg, "enabled", False):
                candidate_pool = getattr(rerank_cfg, "candidate_pool", 50)
                rerank_top_k = getattr(rerank_cfg, "top_k", 20)
                candidates = merged[:candidate_pool]

                # Fetch texts for reranking
                texts = self._fetch_texts(db, [r.item_id for r in candidates])
                if texts:
                    reranked = self._reranker.rerank(query, texts, rerank_top_k)
                    # None means model failed to load — skip reranking, keep RRF order
                    if reranked is not None:
                        reranked_results = []
                        for idx, score in reranked:
                            if idx < len(candidates):
                                r = candidates[idx]
                                r.score = score
                                reranked_results.append(r)
                            else:
                                logger.warning(
                                    "Reranker returned out-of-range index %d (candidates=%d)",
                                    idx, len(candidates),
                                )
                        if reranked_results:
                            merged = reranked_results

        # 5. Apply offset and limit
        return merged[offset:offset + limit]

    def _rrf_fusion(
        self,
        keyword_hits: list[KeywordHit],
        vector_hits: list,
        k: int = 60,
    ) -> list[SearchResult]:
        """Backward-compatible 2-ranker fusion (keyword + vector).

        Preserved for existing callers/tests. Delegates to _rrf_fusion_n.
        """
        return self._rrf_fusion_n(
            [("fts", keyword_hits), ("semantic", vector_hits)], k=k
        )

    def _rrf_fusion_n(
        self,
        rankers: list[tuple[str, list]],
        k: int = 60,
    ) -> list[SearchResult]:
        """Reciprocal Rank Fusion across N named ranker outputs.

        Each ranker is (source_name, hits). Hits just need an ``item_id`` attr.
        KeywordHit's snippets (if present) are captured for the result — fusion
        prefers the first snippet seen per item (FTS wins in practice since it
        runs first and is the only source that carries snippets today).
        """
        scores: dict[str, float] = defaultdict(float)
        sources: dict[str, set] = defaultdict(set)
        snippets: dict[str, tuple] = {}

        for source_name, hits in rankers:
            for rank, hit in enumerate(hits):
                item_id = hit.item_id
                scores[item_id] += 1.0 / (k + rank)
                sources[item_id].add(source_name)
                if item_id not in snippets:
                    title_snip = getattr(hit, "title_snippet", None)
                    content_snip = getattr(hit, "content_snippet", None)
                    if title_snip is not None or content_snip is not None:
                        snippets[item_id] = (title_snip, content_snip)

        results = []
        for item_id, score in sorted(scores.items(), key=lambda x: -x[1]):
            title_snip, content_snip = snippets.get(item_id, (None, None))
            results.append(SearchResult(
                item_id=item_id,
                score=round(score, 6),
                title_snippet=title_snip,
                content_snippet=content_snip,
                sources=list(sources[item_id]),
            ))

        return results

    def _fetch_texts(self, db: Session, item_ids: list[str]) -> list[str]:
        """Fetch item content for reranking."""
        if not item_ids:
            return []
        try:
            from sqlmodel import select

            from fourdpocket.models.item import KnowledgeItem

            items = db.exec(
                select(KnowledgeItem).where(
                    KnowledgeItem.id.in_([uuid.UUID(iid) for iid in item_ids])
                )
            ).all()
            item_map = {str(item.id): item for item in items}

            texts = []
            for iid in item_ids:
                item = item_map.get(iid)
                if item:
                    parts = []
                    if item.title:
                        parts.append(item.title)
                    if item.description:
                        parts.append(item.description)
                    if item.content:
                        parts.append(item.content[:2000])
                    texts.append(" ".join(parts) if parts else "")
                else:
                    texts.append("")
            return texts
        except Exception as e:
            logger.warning("Failed to fetch texts for reranking: %s", e)
            return []
