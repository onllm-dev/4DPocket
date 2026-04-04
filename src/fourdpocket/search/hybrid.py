"""Hybrid search: combine FTS5 keyword results with ChromaDB semantic results via RRF."""

import logging
import uuid
from collections import defaultdict

from sqlmodel import Session

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    fts_results: list[dict],
    semantic_results: list[dict],
    k: int = 60,
) -> list[dict]:
    """Merge two ranked lists using Reciprocal Rank Fusion.

    RRF formula: score(item) = sum(1 / (k + rank)) across all lists.
    k=60 is the standard constant from the original RRF paper.
    """
    scores: dict[str, float] = defaultdict(float)
    sources: dict[str, set] = defaultdict(set)

    for rank, result in enumerate(fts_results):
        item_id = result["item_id"]
        scores[item_id] += 1.0 / (k + rank)
        sources[item_id].add("fts")

    for rank, result in enumerate(semantic_results):
        item_id = result["item_id"]
        scores[item_id] += 1.0 / (k + rank)
        sources[item_id].add("semantic")

    # Build merged results sorted by RRF score
    merged = []
    for item_id, score in sorted(scores.items(), key=lambda x: -x[1]):
        merged.append({
            "item_id": item_id,
            "rrf_score": round(score, 6),
            "sources": list(sources[item_id]),
        })

    return merged


def hybrid_search(
    db: Session,
    query: str,
    user_id: uuid.UUID,
    item_type: str | None = None,
    source_platform: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Run FTS5 + semantic search and merge via RRF."""
    from fourdpocket.search import sqlite_fts

    # FTS5 keyword search — fetch more than needed for good fusion
    fts_results = sqlite_fts.search(
        db, query, user_id,
        item_type=item_type,
        source_platform=source_platform,
        limit=limit * 3,
        offset=0,
    )

    # Semantic search (graceful fallback if embeddings unavailable)
    semantic_results = []
    try:
        from fourdpocket.search.semantic import search_by_text
        raw = search_by_text(query, user_id, limit=limit * 3)
        semantic_results = [{"item_id": r["item_id"]} for r in raw]
    except Exception as e:
        logger.debug("Semantic search unavailable for hybrid: %s", e)

    if not fts_results and not semantic_results:
        return []

    # If only one source has results, return it directly
    if not semantic_results:
        return fts_results[:limit]
    if not fts_results:
        return [{"item_id": r["item_id"], "rank": 0, "title_snippet": None, "content_snippet": None}
                for r in semantic_results[:limit]]

    # Merge via RRF
    merged = reciprocal_rank_fusion(fts_results, semantic_results)

    # Attach FTS snippets where available
    snippet_map = {r["item_id"]: r for r in fts_results}
    results = []
    for item in merged[:limit]:
        fts_data = snippet_map.get(item["item_id"], {})
        results.append({
            "item_id": item["item_id"],
            "rank": item["rrf_score"],
            "title_snippet": fts_data.get("title_snippet"),
            "content_snippet": fts_data.get("content_snippet"),
            "sources": item["sources"],
        })

    return results
