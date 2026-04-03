"""Search API endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, func, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import ItemRead, KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.search.indexer import SearchIndexer

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[ItemRead])
def search_items(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_type: str | None = None,
    source_platform: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Full-text search across knowledge items."""
    indexer = SearchIndexer(db)
    results = indexer.search(
        query=q,
        user_id=current_user.id,
        item_type=item_type,
        source_platform=source_platform,
        limit=limit,
        offset=offset,
    )

    if not results:
        return []

    # Fetch full items by IDs in order
    item_ids = [uuid.UUID(r["item_id"]) for r in results]
    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id.in_(item_ids),  # type: ignore
            KnowledgeItem.user_id == current_user.id,
        )
    ).all()

    # Preserve search result ordering
    item_map = {item.id: item for item in items}
    return [item_map[iid] for iid in item_ids if iid in item_map]


@router.get("/semantic", response_model=list[ItemRead])
def semantic_search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Semantic vector search using embeddings."""
    try:
        from fourdpocket.search.semantic import search_by_text
        results = search_by_text(q, current_user.id, limit=limit)
        if not results:
            return []
        item_ids = [uuid.UUID(r["item_id"]) for r in results]
        items = db.exec(
            select(KnowledgeItem).where(
                KnowledgeItem.id.in_(item_ids),
                KnowledgeItem.user_id == current_user.id,
            )
        ).all()
        item_map = {item.id: item for item in items}
        return [item_map[iid] for iid in item_ids if iid in item_map]
    except Exception:
        return []


@router.get("/filters")
def get_search_filters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return available search filter facets."""
    from fourdpocket.models.base import ItemType
    from fourdpocket.models.tag import Tag

    platform_counts = db.exec(
        select(KnowledgeItem.source_platform, func.count()).where(
            KnowledgeItem.user_id == current_user.id
        ).group_by(KnowledgeItem.source_platform)
    ).all()

    tags = db.exec(
        select(Tag.name, Tag.slug, Tag.usage_count).where(
            Tag.user_id == current_user.id
        ).order_by(col(Tag.usage_count).desc()).limit(50)
    ).all()

    return {
        "platforms": [{"name": str(p), "count": c} for p, c in platform_counts],
        "types": [t.value for t in ItemType],
        "tags": [{"name": n, "slug": s, "count": c} for n, s, c in tags],
    }
