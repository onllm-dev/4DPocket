"""JSON serializers for MCP tool responses.

All helpers take SQLModel rows plus an open session and return a dict that is
safe to ship through a tool call (JSON-serializable, no relationships loaded
implicitly).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlmodel import Session, select

from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.entity import Entity, EntityAlias, ItemEntity
from fourdpocket.models.entity_relation import EntityRelation
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.item_chunk import ItemChunk
from fourdpocket.models.tag import ItemTag, Tag


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None


def knowledge_brief(item: KnowledgeItem) -> dict[str, Any]:
    """Compact item view — used in lists and search results."""
    return {
        "id": str(item.id),
        "title": item.title,
        "url": item.url,
        "item_type": item.item_type.value if item.item_type else None,
        "source_platform": item.source_platform.value if item.source_platform else None,
        "summary": item.summary,
        "is_favorite": bool(item.is_favorite),
        "is_archived": bool(item.is_archived),
        "created_at": _iso(item.created_at),
    }


def knowledge_detail(db: Session, item: KnowledgeItem) -> dict[str, Any]:
    """Full item detail with tags, entities, collections, and excerpts."""
    tag_rows = db.exec(
        select(Tag.name)
        .join(ItemTag, ItemTag.tag_id == Tag.id)
        .where(ItemTag.item_id == item.id)
    ).all()

    entity_rows = db.exec(
        select(Entity)
        .join(ItemEntity, ItemEntity.entity_id == Entity.id)
        .where(ItemEntity.item_id == item.id)
    ).all()

    collection_rows = db.exec(
        select(Collection)
        .join(CollectionItem, CollectionItem.collection_id == Collection.id)
        .where(CollectionItem.item_id == item.id)
    ).all()

    chunk_rows = db.exec(
        select(ItemChunk)
        .where(ItemChunk.item_id == item.id)
        .order_by(ItemChunk.chunk_order)
    ).all()

    return {
        **knowledge_brief(item),
        "description": item.description,
        "content": item.content,
        "author": getattr(item, "author", None),
        "reading_status": (
            item.reading_status.value if getattr(item, "reading_status", None) else None
        ),
        "tags": list(tag_rows),
        "entities": [
            {
                "id": str(e.id),
                "canonical_name": e.canonical_name,
                "entity_type": e.entity_type,
            }
            for e in entity_rows
        ],
        "collections": [
            {"id": str(c.id), "name": c.name} for c in collection_rows
        ],
        "chunk_count": len(chunk_rows),
        "updated_at": _iso(item.updated_at),
    }


def collection_brief(db: Session, collection: Collection) -> dict[str, Any]:
    item_count = len(
        db.exec(
            select(CollectionItem.item_id).where(
                CollectionItem.collection_id == collection.id
            )
        ).all()
    )
    return {
        "id": str(collection.id),
        "name": collection.name,
        "description": collection.description,
        "is_smart": bool(collection.is_smart),
        "item_count": item_count,
    }


def entity_brief(entity: Entity) -> dict[str, Any]:
    return {
        "id": str(entity.id),
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "item_count": entity.item_count,
    }


def entity_with_synthesis(db: Session, entity: Entity) -> dict[str, Any]:
    aliases = db.exec(
        select(EntityAlias.alias).where(EntityAlias.entity_id == entity.id)
    ).all()

    synthesis_raw = getattr(entity, "synthesis", None)
    synthesis_payload: dict | None = None
    if isinstance(synthesis_raw, dict):
        synthesis_payload = synthesis_raw
    elif isinstance(synthesis_raw, str) and synthesis_raw:
        import json

        try:
            synthesis_payload = json.loads(synthesis_raw)
        except (ValueError, TypeError):
            synthesis_payload = {"summary": synthesis_raw}

    return {
        **entity_brief(entity),
        "description": entity.description,
        "aliases": list(aliases),
        "synthesis": synthesis_payload,
        "synthesis_generated_at": _iso(getattr(entity, "synthesis_generated_at", None)),
        "synthesis_confidence": getattr(entity, "synthesis_confidence", None),
    }


def related_entity(entity: Entity, relation: EntityRelation) -> dict[str, Any]:
    return {
        "entity": entity_brief(entity),
        "relation": {
            "keywords": relation.keywords,
            "description": relation.description,
            "weight": relation.weight,
        },
    }


def resolve_entity_ref(
    db: Session, user_id: uuid.UUID, id_or_name: str
) -> Entity | None:
    """Look up an entity by its UUID or canonical_name / alias (case-insensitive)."""
    # Try UUID first
    try:
        parsed = uuid.UUID(id_or_name)
        hit = db.get(Entity, parsed)
        if hit and hit.user_id == user_id:
            return hit
    except ValueError:
        pass

    # Exact name match
    hit = db.exec(
        select(Entity).where(
            Entity.user_id == user_id,
            Entity.canonical_name == id_or_name,
        )
    ).first()
    if hit:
        return hit

    # Alias match
    alias = db.exec(
        select(EntityAlias)
        .join(Entity, Entity.id == EntityAlias.entity_id)
        .where(
            Entity.user_id == user_id,
            EntityAlias.alias == id_or_name,
        )
    ).first()
    if alias:
        return db.get(Entity, alias.entity_id)

    # Fallback: case-insensitive exact match (SQLite LOWER)
    from sqlmodel import func

    lower = id_or_name.lower().strip()
    if lower:
        hit = db.exec(
            select(Entity).where(
                Entity.user_id == user_id,
                func.lower(Entity.canonical_name) == lower,
            )
        ).first()
        if hit:
            return hit
    return None
