"""Search API endpoints — unified search across items + notes with filters and hybrid mode."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, col, func, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import ItemRead, KnowledgeItem
from fourdpocket.models.note import Note, NoteRead
from fourdpocket.models.user import User
from fourdpocket.search.filters import parse_filters

router = APIRouter(prefix="/search", tags=["search"])


def _search_to_items(
    db: Session,
    results: list,
    current_user: User,
) -> list[dict]:
    """Fetch full items by IDs from search results, attach snippets, preserve order."""
    if not results:
        return []

    # Support both dict results and SearchResult dataclasses
    def _get(r, key, default=None):
        if isinstance(r, dict):
            return r.get(key, default)
        return getattr(r, key, default)

    def _item_id(r):
        v = _get(r, "item_id")
        return uuid.UUID(v) if isinstance(v, str) else v

    item_ids = [_item_id(r) for r in results]
    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id.in_(item_ids),
            KnowledgeItem.user_id == current_user.id,
        )
    ).all()

    item_map = {item.id: item for item in items}
    response = []
    for r, iid in zip(results, item_ids):
        if iid in item_map:
            item_dict = ItemRead.model_validate(item_map[iid]).model_dump()
            item_dict["title_snippet"] = _get(r, "title_snippet")
            item_dict["content_snippet"] = _get(r, "content_snippet")
            sources = _get(r, "sources")
            if sources:
                item_dict["sources"] = sources
            response.append(item_dict)
    return response


@router.get("")
def search_items(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_type: str | None = None,
    source_platform: str | None = None,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    tag: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Full-text search across knowledge items with filter pushdown and fuzzy fallback.

    Supports inline filter syntax: `docker tag:devops is:favorite after:2024-01`
    """
    parsed = parse_filters(q)
    search_query = parsed.get("query") or ""
    # If only filters remain (no free text), use original q only if no filters were parsed
    if not search_query and len(parsed) <= 1:
        search_query = q

    effective_type = item_type or parsed.get("item_type")
    effective_platform = source_platform or parsed.get("source_platform")
    effective_favorite = is_favorite if is_favorite is not None else parsed.get("is_favorite")
    effective_archived = is_archived if is_archived is not None else parsed.get("is_archived")
    effective_tags = parsed.get("tags", [])
    if tag:
        effective_tags.append(tag)
    effective_after = after or parsed.get("after")
    effective_before = before or parsed.get("before")

    from fourdpocket.search import get_search_service
    from fourdpocket.search.base import SearchFilters

    service = get_search_service()
    filters = SearchFilters(
        item_type=effective_type,
        source_platform=effective_platform,
        is_favorite=effective_favorite,
        is_archived=effective_archived,
        tags=effective_tags or None,
        after=effective_after,
        before=effective_before,
    )
    results = service.search(
        db, search_query, current_user.id,
        filters=filters,
        limit=limit,
        offset=offset,
    )

    return _search_to_items(db, results, current_user)


@router.get("/unified")
def unified_search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_type: str | None = None,
    source_platform: str | None = None,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    tag: str | None = None,
    after: str | None = None,
    before: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Unified search across items AND notes. Returns both in a single response."""
    # Get item results
    item_results = search_items(
        q=q, db=db, current_user=current_user,
        item_type=item_type, source_platform=source_platform,
        is_favorite=is_favorite, is_archived=is_archived,
        tag=tag, after=after, before=before,
        limit=limit, offset=offset,
    )

    # Get note results
    note_results = []
    try:
        from fourdpocket.config import get_settings
        settings = get_settings()
        if settings.search.backend == "sqlite" and settings.database.url.startswith("sqlite"):
            from fourdpocket.search.sqlite_fts import search_notes as fts_search_notes
            raw_notes = fts_search_notes(db, q, current_user.id, limit=limit, offset=offset)
            if raw_notes:
                note_ids = [uuid.UUID(r["note_id"]) for r in raw_notes]
                notes = db.exec(
                    select(Note).where(Note.id.in_(note_ids), Note.user_id == current_user.id)
                ).all()
                note_map = {n.id: n for n in notes}
                for nid in note_ids:
                    if nid in note_map:
                        note_results.append(NoteRead.model_validate(note_map[nid]).model_dump())
        else:
            # LIKE fallback for non-SQLite
            notes = db.exec(
                select(Note).where(
                    Note.user_id == current_user.id,
                    (Note.title.contains(q)) | (Note.content.contains(q)),
                ).order_by(col(Note.created_at).desc()).limit(limit).offset(offset)
            ).all()
            note_results = [NoteRead.model_validate(n).model_dump() for n in notes]
    except Exception:
        pass

    return {
        "items": item_results,
        "notes": note_results,
        "total": len(item_results) + len(note_results),
    }


@router.get("/hybrid")
def hybrid_search_endpoint(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    item_type: str | None = None,
    source_platform: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    """Hybrid search: combines FTS5 keyword + semantic vector results via Reciprocal Rank Fusion."""
    from fourdpocket.search import get_search_service
    from fourdpocket.search.base import SearchFilters

    service = get_search_service()
    filters = SearchFilters(item_type=item_type, source_platform=source_platform)
    results = service.search(db, q, current_user.id, filters=filters, limit=limit)

    return _search_to_items(db, results, current_user)


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
