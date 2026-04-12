"""Entity API endpoints for the knowledge graph."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.entity import Entity, EntityAlias, ItemEntity
from fourdpocket.models.entity_relation import EntityRelation
from fourdpocket.models.item import ItemRead, KnowledgeItem
from fourdpocket.models.user import User

router = APIRouter(prefix="/entities", tags=["entities"])


def _synthesis_payload(entity: Entity) -> dict | None:
    """Normalise the JSON-typed synthesis column into a dict."""
    raw = entity.synthesis
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        import json

        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {"summary": raw}
    return None


@router.get("/graph")
def graph(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
):
    """Return nodes + edges for the knowledge-graph visualisation."""
    node_query = select(Entity).where(Entity.user_id == current_user.id)
    if entity_type:
        node_query = node_query.where(Entity.entity_type == entity_type)
    nodes = db.exec(
        node_query.order_by(col(Entity.item_count).desc()).limit(limit)
    ).all()
    node_ids = {n.id for n in nodes}

    edges = []
    if node_ids:
        rel_rows = db.exec(
            select(EntityRelation).where(
                EntityRelation.user_id == current_user.id,
                col(EntityRelation.source_id).in_(list(node_ids)),
                col(EntityRelation.target_id).in_(list(node_ids)),
            )
        ).all()
        for r in rel_rows:
            edges.append(
                {
                    "id": str(r.id),
                    "source": str(r.source_id),
                    "target": str(r.target_id),
                    "keywords": r.keywords,
                    "weight": r.weight,
                }
            )

    return {
        "nodes": [
            {
                "id": str(n.id),
                "name": n.canonical_name,
                "entity_type": n.entity_type,
                "item_count": n.item_count,
                "has_synthesis": n.synthesis is not None,
            }
            for n in nodes
        ],
        "edges": edges,
    }


@router.get("")
def list_entities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_type: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """List user's entities, optionally filtered by type or name search."""
    query = select(Entity).where(Entity.user_id == current_user.id)

    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if q:
        query = query.where(Entity.canonical_name.contains(q))

    query = query.order_by(col(Entity.item_count).desc()).offset(offset).limit(limit)
    entities = db.exec(query).all()

    return [
        {
            "id": str(e.id),
            "canonical_name": e.canonical_name,
            "entity_type": e.entity_type,
            "description": e.description,
            "item_count": e.item_count,
            "has_synthesis": e.synthesis is not None,
            "synthesis_confidence": e.synthesis_confidence,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entities
    ]


@router.get("/{entity_id}")
def get_entity(
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get entity detail with aliases."""
    entity = db.get(Entity, entity_id)
    if not entity or entity.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Entity not found")

    aliases = db.exec(
        select(EntityAlias).where(EntityAlias.entity_id == entity_id)
    ).all()

    return {
        "id": str(entity.id),
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "description": entity.description,
        "item_count": entity.item_count,
        "aliases": [{"alias": a.alias, "source": a.source} for a in aliases],
        "synthesis": _synthesis_payload(entity),
        "synthesis_generated_at": (
            entity.synthesis_generated_at.isoformat()
            if entity.synthesis_generated_at
            else None
        ),
        "synthesis_confidence": entity.synthesis_confidence,
        "synthesis_item_count": entity.synthesis_item_count,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
    }


@router.post("/{entity_id}/synthesize")
def regenerate_synthesis(
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    force: bool = False,
):
    """Regenerate the synthesis for a single entity.

    By default respects ``min_interval_hours``; pass ``force=true`` to bypass
    the cooldown (but not the ``min_item_count`` guard).
    """
    entity = db.get(Entity, entity_id)
    if not entity or entity.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Entity not found")

    from fourdpocket.ai.synthesizer import should_regenerate, synthesize_entity
    from fourdpocket.config import get_settings

    settings = get_settings().enrichment
    if entity.item_count < settings.synthesis_min_item_count:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Entity has only {entity.item_count} mentions "
                f"(minimum {settings.synthesis_min_item_count} required)."
            ),
        )

    if not force and not should_regenerate(entity):
        raise HTTPException(
            status_code=429,
            detail="Synthesis was regenerated recently. Pass force=true to override.",
        )

    payload = synthesize_entity(entity.id, db)
    if payload is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Synthesis could not be generated (no evidence or LLM unavailable)."
            ),
        )
    return {"status": "regenerated", "synthesis": payload}


@router.get("/{entity_id}/items")
def get_entity_items(
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Get items that mention this entity."""
    entity = db.get(Entity, entity_id)
    if not entity or entity.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Entity not found")

    item_links = db.exec(
        select(ItemEntity)
        .where(ItemEntity.entity_id == entity_id)
        .order_by(col(ItemEntity.salience).desc())
        .offset(offset)
        .limit(limit)
    ).all()

    item_ids = [ie.item_id for ie in item_links]
    if not item_ids:
        return []

    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id.in_(item_ids),
            KnowledgeItem.user_id == current_user.id,
        )
    ).all()

    item_map = {item.id: item for item in items}
    salience_map = {ie.item_id: ie.salience for ie in item_links}

    return [
        {
            **ItemRead.model_validate(item_map[iid]).model_dump(),
            "salience": salience_map.get(iid, 0),
        }
        for iid in item_ids
        if iid in item_map
    ]


@router.get("/{entity_id}/related")
def get_related_entities(
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get entities related to this one via the concept graph."""
    entity = db.get(Entity, entity_id)
    if not entity or entity.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Entity not found")

    # Find relations where this entity is source or target
    relations = db.exec(
        select(EntityRelation).where(
            EntityRelation.user_id == current_user.id,
            (EntityRelation.source_id == entity_id) | (EntityRelation.target_id == entity_id),
        ).order_by(col(EntityRelation.weight).desc()).limit(limit)
    ).all()

    results = []
    for r in relations:
        other_id = r.target_id if r.source_id == entity_id else r.source_id
        other = db.get(Entity, other_id)
        if other:
            results.append({
                "entity": {
                    "id": str(other.id),
                    "canonical_name": other.canonical_name,
                    "entity_type": other.entity_type,
                    "item_count": other.item_count,
                },
                "relation": {
                    "keywords": r.keywords,
                    "description": r.description,
                    "weight": r.weight,
                    "item_count": r.item_count,
                },
            })

    return results
