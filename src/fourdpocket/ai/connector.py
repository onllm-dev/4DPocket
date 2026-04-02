"""Related items engine — finds connections between knowledge items."""

import logging
import uuid
from dataclasses import dataclass

from sqlmodel import Session, select, col

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.tag import ItemTag

logger = logging.getLogger(__name__)


@dataclass
class RelatedItem:
    item_id: uuid.UUID
    score: float
    signals: list[str]


def find_related(
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
    limit: int = 5,
) -> list[RelatedItem]:
    """Find items related to the given item using 3 weighted signals.

    Signals:
    1. Shared tags (weight 0.3)
    2. Same source/author (weight 0.2)
    3. Semantic similarity (weight 0.5) — requires ChromaDB

    Returns top N related items sorted by combined score.
    """
    item = db.get(KnowledgeItem, item_id)
    if not item:
        return []

    scores: dict[uuid.UUID, dict] = {}

    # Signal 1: Shared tags (weight 0.3)
    item_tag_ids = db.exec(
        select(ItemTag.tag_id).where(ItemTag.item_id == item_id)
    ).all()

    if item_tag_ids:
        # Find other items sharing these tags
        shared = db.exec(
            select(ItemTag.item_id, ItemTag.tag_id).where(
                ItemTag.tag_id.in_(item_tag_ids),
                ItemTag.item_id != item_id,
            )
        ).all()

        for other_id, _tag_id in shared:
            # Verify user ownership
            other = db.get(KnowledgeItem, other_id)
            if other and other.user_id == user_id:
                if other_id not in scores:
                    scores[other_id] = {"score": 0.0, "signals": []}
                scores[other_id]["score"] += 0.3 / max(len(item_tag_ids), 1)
                if "shared_tags" not in scores[other_id]["signals"]:
                    scores[other_id]["signals"].append("shared_tags")

    # Signal 2: Same source/domain (weight 0.2)
    if item.url:
        from urllib.parse import urlparse
        domain = urlparse(item.url).netloc
        if domain:
            same_domain = db.exec(
                select(KnowledgeItem).where(
                    KnowledgeItem.user_id == user_id,
                    KnowledgeItem.id != item_id,
                    KnowledgeItem.url.isnot(None),
                )
            ).all()

            for other in same_domain:
                if other.url:
                    other_domain = urlparse(other.url).netloc
                    if other_domain == domain:
                        if other.id not in scores:
                            scores[other.id] = {"score": 0.0, "signals": []}
                        scores[other.id]["score"] += 0.2
                        scores[other.id]["signals"].append("same_source")

    # Signal 3: Semantic similarity (weight 0.5)
    try:
        from fourdpocket.search.semantic import query_similar
        similar = query_similar(item_id, user_id, limit=limit * 2)
        for result in similar:
            other_id = uuid.UUID(result["item_id"])
            if other_id != item_id:
                if other_id not in scores:
                    scores[other_id] = {"score": 0.0, "signals": []}
                scores[other_id]["score"] += 0.5 * result.get("similarity", 0.5)
                scores[other_id]["signals"].append("semantic")
    except Exception as e:
        logger.debug("Semantic similarity unavailable: %s", e)

    # Sort by score and return top N
    ranked = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    return [
        RelatedItem(
            item_id=rid,
            score=round(data["score"], 3),
            signals=data["signals"],
        )
        for rid, data in ranked[:limit]
    ]


def find_related_on_save(
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
    limit: int = 5,
) -> list[RelatedItem]:
    """Fast variant for on-save — uses only semantic similarity."""
    try:
        from fourdpocket.search.semantic import query_similar
        similar = query_similar(item_id, user_id, limit=limit)
        return [
            RelatedItem(
                item_id=uuid.UUID(r["item_id"]),
                score=round(r.get("similarity", 0.5), 3),
                signals=["semantic"],
            )
            for r in similar
            if uuid.UUID(r["item_id"]) != item_id
        ]
    except Exception as e:
        logger.debug("Semantic search unavailable for on-save related: %s", e)
        return []
