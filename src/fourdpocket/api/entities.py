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


@router.get("")
def list_entities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_type: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
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
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
    }


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
