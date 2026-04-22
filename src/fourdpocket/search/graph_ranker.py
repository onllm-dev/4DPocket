"""Graph-anchored ranker — third RRF input sourced from the concept graph.

Given a free-text query, find entities whose canonical_name or alias matches
a query token, expand one hop through EntityRelation, and aggregate the items
those entities mention. Items are scored by ItemEntity.salience, weighted by
relation weight + hop_decay for neighbor-reached entities.

Output is a list[GraphHit] sorted by score descending. Fusion treats this as
just another ranker — the score is ordering-only; RRF uses rank position.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from sqlmodel import Session, or_, select

from fourdpocket.models.entity import Entity, EntityAlias, ItemEntity
from fourdpocket.models.entity_relation import EntityRelation
from fourdpocket.search.base import GraphHit

logger = logging.getLogger(__name__)


# Minimal stopword list — matches existing project style (no NLP deps).
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "of", "at", "by", "for",
    "with", "about", "to", "from", "in", "on", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "this", "that", "these", "those", "it", "its", "as", "what", "which",
    "who", "whom", "how", "why", "when", "where",
})


def _tokenize(query: str) -> list[str]:
    """Lowercase, strip, filter stopwords and short tokens (min length 3)."""
    if not query:
        return []
    tokens = []
    for raw in query.split():
        t = raw.strip().lower().strip(".,;:!?\"'()[]{}")
        if len(t) >= 3 and t not in _STOPWORDS:
            tokens.append(t)
    return tokens


def graph_anchored_hits(
    db: Session,
    query: str,
    user_id: uuid.UUID,
    k: int = 50,
    hop_decay: float | None = None,
) -> list[GraphHit]:
    """Rank items via entity + 1-hop relation lookup.

    Args:
        db: SQLModel session
        query: free-text query
        user_id: user scope
        k: max items to return
        hop_decay: neighbor score multiplier (0.0-1.0); reads from settings if None
    """
    if hop_decay is None:
        try:
            from fourdpocket.config import get_settings
            hop_decay = get_settings().search.graph_ranker_hop_decay
        except Exception:
            hop_decay = 0.5

    tokens = _tokenize(query)
    if not tokens:
        return []

    try:
        # 1. Seed entities: canonical_name OR alias substring match per token
        name_clauses = [Entity.canonical_name.ilike(f"%{t}%") for t in tokens]
        seed_by_name = db.exec(
            select(Entity).where(
                Entity.user_id == user_id,
                or_(*name_clauses),
            ).limit(200)
        ).all()

        alias_clauses = [EntityAlias.alias.ilike(f"%{t}%") for t in tokens]
        aliases = db.exec(
            select(EntityAlias)
            .join(Entity, Entity.id == EntityAlias.entity_id)
            .where(Entity.user_id == user_id, or_(*alias_clauses))
            .limit(200)
        ).all()
        alias_entity_ids = {a.entity_id for a in aliases}
        seed_by_alias = []
        if alias_entity_ids:
            seed_by_alias = db.exec(
                select(Entity).where(
                    Entity.user_id == user_id,
                    Entity.id.in_(alias_entity_ids),
                )
            ).all()

        seed_map: dict[uuid.UUID, Entity] = {e.id: e for e in seed_by_name}
        for e in seed_by_alias:
            seed_map.setdefault(e.id, e)

        if not seed_map:
            return []

        seed_ids = set(seed_map.keys())
        seed_ids_list = list(seed_ids)

        # 2. 1-hop neighbors via EntityRelation.
        rels = db.exec(
            select(EntityRelation).where(
                EntityRelation.user_id == user_id,
                or_(
                    EntityRelation.source_id.in_(seed_ids_list),
                    EntityRelation.target_id.in_(seed_ids_list),
                ),
            ).limit(1000)
        ).all()

        # entity_id -> effective score contribution (1.0 for seed, w*hop_decay for neighbor)
        entity_weight: dict[uuid.UUID, float] = {eid: 1.0 for eid in seed_ids}
        for r in rels:
            neighbor_id = r.target_id if r.source_id in seed_ids else r.source_id
            contribution = float(r.weight) * hop_decay
            # Keep the strongest edge if we reach the same neighbor through multiple seeds
            if contribution > entity_weight.get(neighbor_id, 0.0):
                entity_weight[neighbor_id] = contribution

        # 3. Gather items via ItemEntity for all involved entities — user-scoped via join
        from fourdpocket.models.item import KnowledgeItem

        all_entity_ids = list(entity_weight.keys())
        item_links = db.exec(
            select(ItemEntity)
            .join(KnowledgeItem, KnowledgeItem.id == ItemEntity.item_id)
            .where(
                ItemEntity.entity_id.in_(all_entity_ids),
                KnowledgeItem.user_id == user_id,
            )
        ).all()

        # 4. Sum scores per item
        item_scores: dict[str, float] = defaultdict(float)
        for link in item_links:
            w = entity_weight.get(link.entity_id, 0.0)
            if w <= 0.0:
                continue
            item_scores[str(link.item_id)] += float(link.salience) * w

        # 5. Sort and return top-k
        ranked = sorted(item_scores.items(), key=lambda kv: -kv[1])[:k]
        return [GraphHit(item_id=iid, score=score) for iid, score in ranked]

    except Exception as e:
        # Graph ranker is a best-effort third voice; never block search.
        logger.warning("Graph ranker failed: %s", e)
        return []
