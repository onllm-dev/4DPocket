"""Saved search filters (smart filters) endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import (
    get_current_user,
    get_db,
    require_pat_deletion,
    require_pat_editor,
)
from fourdpocket.models.saved_filter import SavedFilter
from fourdpocket.models.user import User

router = APIRouter(prefix="/filters", tags=["Saved Filters"])


class FilterCreate(BaseModel):
    name: str
    query: str
    filters: dict = {}


class FilterUpdate(BaseModel):
    name: str | None = None
    query: str | None = None
    filters: dict | None = None


# Alias used in endpoint signatures
SavedFilterUpdate = FilterUpdate


@router.get("")
def list_filters(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.exec(
        select(SavedFilter).where(SavedFilter.user_id == current_user.id).order_by(SavedFilter.created_at.desc())
    ).all()


@router.post("", status_code=201)
def create_filter(
    body: FilterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    f = SavedFilter(user_id=current_user.id, name=body.name, query=body.query, filters=body.filters)
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.delete("/{filter_id}", status_code=204)
def delete_filter(
    filter_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_deletion),
):
    f = db.exec(select(SavedFilter).where(SavedFilter.id == filter_id, SavedFilter.user_id == current_user.id)).first()
    if not f:
        raise HTTPException(status_code=404, detail="Filter not found")
    db.delete(f)
    db.commit()


@router.patch("/{filter_id}")
def update_saved_filter(
    filter_id: uuid.UUID,
    body: SavedFilterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    sf = db.exec(
        select(SavedFilter).where(
            SavedFilter.id == filter_id,
            SavedFilter.user_id == current_user.id,
        )
    ).first()
    if not sf:
        raise HTTPException(status_code=404, detail="Filter not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(sf, field, value)
    db.commit()
    db.refresh(sf)
    return sf


@router.get("/{filter_id}/execute")
def execute_saved_filter(
    filter_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    sf = db.exec(
        select(SavedFilter).where(
            SavedFilter.id == filter_id,
            SavedFilter.user_id == current_user.id,
        )
    ).first()
    if not sf:
        raise HTTPException(status_code=404, detail="Filter not found")

    from fourdpocket.search import get_search_service
    from fourdpocket.search.base import SearchFilters

    service = get_search_service()

    sf_filters = sf.filters or {}
    search_filters = SearchFilters(
        item_type=sf_filters.get("item_type"),
        source_platform=sf_filters.get("source_platform"),
    )
    results = service.search(
        db,
        query=sf.query or "",
        user_id=current_user.id,
        filters=search_filters,
        limit=limit,
        offset=offset,
    )

    if not results:
        return []

    from fourdpocket.models.item import KnowledgeItem

    item_ids = [uuid.UUID(getattr(r, "item_id", None) or r["item_id"]) for r in results]
    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id.in_(item_ids),
            KnowledgeItem.user_id == current_user.id,
        )
    ).all()
    item_map = {item.id: item for item in items}
    return [item_map[iid] for iid in item_ids if iid in item_map]
