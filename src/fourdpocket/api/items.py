"""Knowledge item CRUD endpoints."""

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, col, select
from sqlmodel import delete as sql_delete

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.base import ItemType, ReadingStatus, SourcePlatform
from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.models.item import (
    ItemCreate,
    ItemRead,
    ItemUpdate,
    KnowledgeItem,
)
from fourdpocket.models.tag import ItemTag, Tag
from fourdpocket.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items", tags=["items"])


def _is_safe_proxy_url(url: str) -> bool:
    """Validate URL is safe for server-side fetching (no internal networks)."""
    import ipaddress
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    if hostname in ("localhost", ""):
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        # hostname is not an IP, check for common internal patterns
        if hostname.endswith(".local") or hostname.endswith(".internal"):
            return False
    return True


def _try_sync_enrich(item: KnowledgeItem, db: Session, user_id: uuid.UUID) -> None:
    """Run lightweight synchronous AI enrichment (tagging + summarization).

    Skips if:
    - sync_enrichment is disabled in config
    - item already has AI-generated tags (avoids duplicate enrichment)
    - AI provider is not configured
    """
    from fourdpocket.ai.factory import get_resolved_ai_config

    config = get_resolved_ai_config()
    if not config.get("sync_enrichment", True):
        return

    # Skip if item already has tags (Huey may have already processed it)
    existing_tags = db.exec(
        select(ItemTag).where(ItemTag.item_id == item.id)
    ).first()
    if existing_tags:
        return

    # For URL items: skip inline content fetching (too slow) - let Huey handle it.
    # Just run lightweight tagging + summarization on whatever content is already set.
    try:
        from fourdpocket.ai.sanitizer import sanitize_for_prompt
        from fourdpocket.ai.tagger import auto_tag_item

        auto_tag_item(
            item_id=item.id,
            user_id=user_id,
            title=sanitize_for_prompt(item.title or "", max_length=2000),
            content=sanitize_for_prompt(item.content or "", max_length=4000),
            description=sanitize_for_prompt(item.description or "", max_length=1000),
            db=db,
        )
    except Exception as e:
        logger.warning("Sync tagging failed for item %s: %s", item.id, e)

    try:
        from fourdpocket.ai.summarizer import summarize_item

        summarize_item(item.id, db)
    except Exception as e:
        logger.warning("Sync summarization failed for item %s: %s", item.id, e)

    # Re-index with enriched content
    try:
        from fourdpocket.search import get_search_service

        get_search_service().index_item(db, item)
    except Exception:
        pass


def _detect_platform(url: str) -> SourcePlatform:
    """Detect source platform from URL."""
    url_lower = url.lower()
    patterns = {
        SourcePlatform.youtube: ["youtube.com", "youtu.be"],
        SourcePlatform.reddit: ["reddit.com", "redd.it"],
        SourcePlatform.github: ["github.com", "gist.github.com"],
        SourcePlatform.twitter: ["twitter.com", "x.com"],
        SourcePlatform.instagram: ["instagram.com"],
        SourcePlatform.threads: ["threads.net"],
        SourcePlatform.tiktok: ["tiktok.com"],
        SourcePlatform.hackernews: ["news.ycombinator.com"],
        SourcePlatform.stackoverflow: ["stackoverflow.com"],
        SourcePlatform.mastodon: [],  # detected by ActivityPub patterns
        SourcePlatform.substack: ["substack.com"],
        SourcePlatform.medium: ["medium.com"],
        SourcePlatform.linkedin: ["linkedin.com"],
        SourcePlatform.spotify: ["open.spotify.com"],
    }
    for platform, domains in patterns.items():
        if any(domain in url_lower for domain in domains):
            return platform
    return SourcePlatform.generic


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(
    item_data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    platform = item_data.source_platform
    if item_data.url and platform == SourcePlatform.generic:
        platform = _detect_platform(item_data.url)

    # Check for duplicate URL
    if item_data.url:
        existing = db.exec(
            select(KnowledgeItem).where(
                KnowledgeItem.user_id == current_user.id,
                KnowledgeItem.url == item_data.url,
            )
        ).first()
        if existing:
            raise HTTPException(
                409,
                detail="You already saved this URL",
            )

    item = KnowledgeItem(
        user_id=current_user.id,
        url=item_data.url,
        title=item_data.title,
        description=item_data.description,
        content=item_data.content,
        item_type=item_data.item_type,
        source_platform=platform,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    # Index for search
    try:
        from fourdpocket.search import get_search_service

        get_search_service().index_item(db, item)
    except Exception:
        pass  # Search indexing is best-effort

    # Run automation rules
    try:
        from fourdpocket.workers.rule_engine import run_rules_for_item

        run_rules_for_item(item, db)
    except Exception:
        pass  # Rules are best-effort

    # Dispatch background processing workers (full pipeline with embeddings)
    try:
        if item.url:
            from fourdpocket.workers.fetcher import fetch_and_process_url
            from fourdpocket.workers.screenshot import capture_screenshot
            fetch_and_process_url(str(item.id), item.url, str(current_user.id))
            capture_screenshot(str(item.id), item.url, str(current_user.id))
        else:
            from fourdpocket.workers.enrichment_pipeline import enrich_item_v2
            enrich_item_v2(str(item.id), str(current_user.id))
    except Exception:
        pass  # Worker dispatch is best-effort

    # Sync enrichment fallback: if Huey worker is not running, enrich inline
    _try_sync_enrich(item, db, current_user.id)

    return item


@router.get("", response_model=list[ItemRead])
def list_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    item_type: ItemType | None = None,
    source_platform: SourcePlatform | None = None,
    is_favorite: bool | None = None,
    is_archived: bool | None = None,
    tag_id: uuid.UUID | None = None,
    sort_by: str = Query(default="created_at", pattern="^(created_at|title|updated_at)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    query = select(KnowledgeItem).where(KnowledgeItem.user_id == current_user.id)

    if item_type is not None:
        query = query.where(KnowledgeItem.item_type == item_type)
    if source_platform is not None:
        query = query.where(KnowledgeItem.source_platform == source_platform)
    if is_favorite is not None:
        query = query.where(KnowledgeItem.is_favorite == is_favorite)
    if is_archived is not None:
        query = query.where(KnowledgeItem.is_archived == is_archived)
    if tag_id is not None:
        query = query.join(ItemTag, ItemTag.item_id == KnowledgeItem.id).where(
            ItemTag.tag_id == tag_id
        )

    sort_col = getattr(KnowledgeItem, sort_by)
    if sort_order == "desc":
        query = query.order_by(col(sort_col).desc())
    else:
        query = query.order_by(col(sort_col).asc())

    query = query.offset(offset).limit(limit)
    items = db.exec(query).all()

    # Batch-fetch tags + enrichment status for all items (avoids N+1)
    if items:
        item_ids = [i.id for i in items]
        tag_rows = db.exec(
            select(ItemTag.item_id, Tag.id, Tag.name, Tag.color)
            .join(Tag, Tag.id == ItemTag.tag_id)
            .where(ItemTag.item_id.in_(item_ids))
        ).all()
        tags_by_item: dict[uuid.UUID, list[dict]] = {}
        for row in tag_rows:
            tags_by_item.setdefault(row[0], []).append(
                {"id": str(row[1]), "name": row[2], "color": row[3]}
            )

        from fourdpocket.workers.enrichment_summary import batch_enrichment_summary
        enrich_by_item = batch_enrichment_summary(db, item_ids)

        result = []
        for item in items:
            d = item.model_dump()
            d["tags"] = tags_by_item.get(item.id, [])
            summary = enrich_by_item.get(item.id)
            d["enrichment_status"] = summary.model_dump() if summary else None
            result.append(d)
        return result

    return items


@router.get("/timeline")
def get_timeline(
    days: int = Query(default=30, ge=1, le=365),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get items grouped by date for timeline view."""
    from collections import defaultdict
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)
    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.user_id == user.id,
            KnowledgeItem.created_at >= since,
        ).order_by(KnowledgeItem.created_at.desc()).offset(offset).limit(limit)
    ).all()

    # Group by date
    grouped = defaultdict(list)
    for item in items:
        date_key = item.created_at.strftime("%Y-%m-%d") if item.created_at else "unknown"
        grouped[date_key].append({
            "id": str(item.id),
            "title": item.title,
            "url": item.url,
            "source_platform": item.source_platform,
            "item_type": item.item_type,
            "summary": item.summary,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        })

    return [{"date": date, "items": items} for date, items in sorted(grouped.items(), reverse=True)]


@router.get("/reading-queue")
def get_reading_queue(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get items in reading queue (has content, not fully read)."""
    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.user_id == user.id,
            KnowledgeItem.content.is_not(None),
            KnowledgeItem.is_archived == False,  # noqa: E712
            KnowledgeItem.reading_progress < 100,
        ).order_by(KnowledgeItem.created_at.desc()).limit(50)
    ).all()
    return items


@router.get("/reading-list", response_model=list[ItemRead])
def get_reading_list(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get items where reading_status is 'reading_list'."""
    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.user_id == current_user.id,
            KnowledgeItem.reading_status == ReadingStatus.reading_list,
        )
        .order_by(col(KnowledgeItem.created_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return items


@router.get("/read", response_model=list[ItemRead])
def get_read_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get items where reading_status is 'read'."""
    items = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.user_id == current_user.id,
            KnowledgeItem.reading_status == ReadingStatus.read,
        )
        .order_by(col(KnowledgeItem.created_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return items


@router.get("/check-url")
def check_url(
    url: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if a URL is already saved by the current user."""
    item = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.user_id == current_user.id,
            KnowledgeItem.url == url,
        )
    ).first()
    if item:
        return {"exists": True, "item_id": str(item.id), "title": item.title}
    return {"exists": False}


@router.get("/queue-stats")
def get_queue_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a cheap snapshot of in-flight enrichment work for the user.

    Used by the UI to show "~N items ahead" hints on pending items.
    Intentionally not an ETA — queue depth alone is honest.
    """
    from fourdpocket.workers.enrichment_summary import queue_stats
    return queue_stats(db, current_user.id)


@router.get("/{item_id}", response_model=ItemRead)
def get_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Attach enrichment summary so the detail page can show the same badge
    from fourdpocket.workers.enrichment_summary import batch_enrichment_summary
    summaries = batch_enrichment_summary(db, [item.id])
    payload = item.model_dump()
    summary = summaries.get(item.id)
    payload["enrichment_status"] = summary.model_dump() if summary else None
    return payload


@router.get("/{item_id}/tags")
def get_item_tags(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all tags linked to an item."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    rows = db.exec(
        select(Tag, ItemTag.confidence).join(ItemTag, ItemTag.tag_id == Tag.id).where(
            ItemTag.item_id == item_id
        )
    ).all()

    return [
        {
            "tag_id": str(tag.id),
            "tag_name": tag.name,
            "tag_slug": tag.slug,
            "tag_color": tag.color,
            "confidence": confidence or 0,
            "ai_generated": tag.ai_generated,
        }
        for tag, confidence in rows
    ]


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(
    item_id: uuid.UUID,
    item_data: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    update_dict = item_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def cascade_delete_item(db: Session, item: KnowledgeItem) -> None:
    """Delete an item and every row that references it.

    Shared between the REST ``DELETE /items/{id}`` handler and the MCP
    ``delete_knowledge`` tool so both enforce identical cleanup (FK-safe,
    search indexes purged). Caller commits.
    """
    from fourdpocket.models.collection import CollectionItem
    from fourdpocket.models.comment import Comment
    from fourdpocket.models.embedding import Embedding
    from fourdpocket.models.entity import ItemEntity
    from fourdpocket.models.entity_relation import RelationEvidence
    from fourdpocket.models.highlight import Highlight
    from fourdpocket.models.item_chunk import ItemChunk
    from fourdpocket.models.item_link import ItemLink
    from fourdpocket.models.share import Share, ShareRecipient

    item_id = item.id
    user_id = item.user_id

    # Decrement tag usage counts before removing links
    for tag_link in db.exec(select(ItemTag).where(ItemTag.item_id == item_id)).all():
        tag = db.get(Tag, tag_link.tag_id)
        if tag and tag.usage_count > 0:
            tag.usage_count = tag.usage_count - 1
            db.add(tag)
        db.delete(tag_link)

    # Delete relation evidence referencing this item (before relations)
    for ev in db.exec(
        select(RelationEvidence).where(RelationEvidence.item_id == item_id)
    ).all():
        db.delete(ev)

    # Delete item-entity links
    for ie in db.exec(select(ItemEntity).where(ItemEntity.item_id == item_id)).all():
        db.delete(ie)

    # Delete enrichment stage records
    for es in db.exec(
        select(EnrichmentStage).where(EnrichmentStage.item_id == item_id)
    ).all():
        db.delete(es)

    # Delete chunks (DB rows — FTS + vector cleanup handled by SearchService below)
    for chunk in db.exec(select(ItemChunk).where(ItemChunk.item_id == item_id)).all():
        db.delete(chunk)

    for model, fk in [
        (Highlight, Highlight.item_id),
        (Comment, Comment.item_id),
        (Embedding, Embedding.item_id),
        (CollectionItem, CollectionItem.item_id),
        (ItemLink, ItemLink.item_id),
    ]:
        for row in db.exec(select(model).where(fk == item_id)).all():
            db.delete(row)

    # Delete shares referencing this item
    for share in db.exec(select(Share).where(Share.item_id == item_id)).all():
        for sr in db.exec(
            select(ShareRecipient).where(ShareRecipient.share_id == share.id)
        ).all():
            db.delete(sr)
        db.delete(share)

    # Remove from all search indexes (FTS, chunks_fts, vector embeddings)
    try:
        from fourdpocket.search import get_search_service
        get_search_service().delete_item(db, item_id, user_id)
    except Exception:
        pass

    # Flush so dependent rows are gone before the parent delete hits SQLite FK check
    db.flush()
    db.delete(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    cascade_delete_item(db, item)
    db.commit()


@router.post("/{item_id}/tags", status_code=status.HTTP_201_CREATED)
def add_tag_to_item(
    item_id: uuid.UUID,
    tag_id: uuid.UUID = Query(...),
    confidence: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    tag = db.get(Tag, tag_id)
    if not tag or tag.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    existing = db.exec(
        select(ItemTag).where(ItemTag.item_id == item_id, ItemTag.tag_id == tag_id)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already applied")

    link = ItemTag(item_id=item_id, tag_id=tag_id, confidence=confidence)
    db.add(link)

    tag.usage_count += 1
    db.add(tag)

    db.commit()
    return {"item_id": str(item_id), "tag_id": str(tag_id), "confidence": confidence}


@router.delete("/{item_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_tag_from_item(
    item_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    link = db.exec(
        select(ItemTag).where(ItemTag.item_id == item_id, ItemTag.tag_id == tag_id)
    ).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not applied")

    tag = db.get(Tag, tag_id)
    if tag and tag.usage_count > 0:
        tag.usage_count -= 1
        db.add(tag)

    db.delete(link)
    db.commit()


@router.post("/{item_id}/archive", status_code=202)
def archive_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger full-page archival as background task."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    if not item.url:
        raise HTTPException(status_code=400, detail="Item has no URL to archive")
    try:
        from fourdpocket.workers.archiver import archive_page
        archive_page(str(item_id), item.url, str(current_user.id))
    except Exception:
        pass  # Worker may not be running
    return {"status": "queued", "item_id": str(item_id)}


@router.post("/{item_id}/reprocess", status_code=202)
def reprocess_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-run platform processor on the URL."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    if not item.url:
        raise HTTPException(status_code=400, detail="Item has no URL to reprocess")
    try:
        from fourdpocket.workers.fetcher import fetch_and_process_url
        fetch_and_process_url(str(item_id), item.url, str(current_user.id))
    except Exception:
        pass
    return {"status": "queued", "item_id": str(item_id)}


@router.get("/{item_id}/related")
def get_related_items(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=5, ge=1, le=20),
):
    """Get AI-suggested related items."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item not found")
    try:
        from fourdpocket.ai.connector import find_related
        related = find_related(item_id, current_user.id, db, limit=limit)
        result = []
        for r in related:
            related_item = db.get(KnowledgeItem, r.item_id)
            if related_item:
                result.append({
                    "id": str(related_item.id),
                    "title": related_item.title,
                    "url": related_item.url,
                    "source_platform": (
                        related_item.source_platform.value
                        if related_item.source_platform
                        else "generic"
                    ),
                    "score": r.score,
                    "signals": r.signals,
                })
        return result
    except Exception:
        return []


@router.get("/{item_id}/enrichment")
def get_enrichment_status(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get per-stage enrichment status for an item."""
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Item not found")

    from sqlmodel import select


    stages = db.exec(
        select(EnrichmentStage).where(EnrichmentStage.item_id == item_id)
    ).all()

    return [
        {
            "stage": s.stage,
            "status": s.status,
            "attempts": s.attempts,
            "error": s.last_error,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "finished_at": s.finished_at.isoformat() if s.finished_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in stages
    ]


class ReadingProgressUpdate(BaseModel):
    progress: int = Field(ge=0, le=100)


@router.patch("/{item_id}/reading-progress")
def update_reading_progress(
    item_id: uuid.UUID,
    body: ReadingProgressUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update reading progress for read-it-later mode."""
    item = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id, KnowledgeItem.user_id == user.id
        )
    ).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item.reading_progress = body.progress
    db.commit()
    return {"status": "updated", "reading_progress": body.progress}


class BulkAction(str, Enum):
    tag = "tag"
    archive = "archive"
    delete = "delete"
    favorite = "favorite"
    unfavorite = "unfavorite"
    enrich = "enrich"


class BulkActionRequest(BaseModel):
    action: BulkAction
    item_ids: list[uuid.UUID]
    tag_id: uuid.UUID | None = None
    tag_name: str | None = None

    @field_validator("item_ids")
    @classmethod
    def validate_item_ids(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(v) > 500:
            raise ValueError("Maximum 500 items per bulk action")
        return v


@router.post("/bulk")
def bulk_action(
    data: BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Perform bulk action on selected items."""
    processed = 0
    for iid in data.item_ids:
        item = db.get(KnowledgeItem, iid)
        if not item or item.user_id != current_user.id:
            continue

        if data.action == "archive":
            item.is_archived = True
            db.add(item)
        elif data.action == "delete":
            from fourdpocket.models.enrichment import EnrichmentStage as _ES
            from fourdpocket.models.entity import ItemEntity as _IE
            from fourdpocket.models.entity_relation import RelationEvidence as _RE
            from fourdpocket.models.item_chunk import ItemChunk as _IC
            db.exec(sql_delete(_RE).where(_RE.item_id == item.id))
            db.exec(sql_delete(_IE).where(_IE.item_id == item.id))
            db.exec(sql_delete(_ES).where(_ES.item_id == item.id))
            db.exec(sql_delete(_IC).where(_IC.item_id == item.id))
            db.exec(sql_delete(ItemTag).where(ItemTag.item_id == item.id))
            try:
                from fourdpocket.search import get_search_service
                get_search_service().delete_item(db, item.id, current_user.id)
            except Exception:
                pass
            db.delete(item)
        elif data.action == "favorite":
            item.is_favorite = True
            db.add(item)
        elif data.action == "unfavorite":
            item.is_favorite = False
            db.add(item)
        elif data.action == "tag":
            # Resolve tag by ID or name (create if needed)
            tag = None
            if data.tag_id:
                tag = db.get(Tag, data.tag_id)
            elif data.tag_name:
                slug = data.tag_name.strip().lower().replace(" ", "-")
                tag = db.exec(
                    select(Tag).where(Tag.user_id == current_user.id, Tag.slug == slug)
                ).first()
                if not tag:
                    tag = Tag(
                        user_id=current_user.id,
                        name=data.tag_name.strip(),
                        slug=slug,
                    )
                    db.add(tag)
                    db.flush()
            if tag and tag.user_id == current_user.id:
                existing = db.exec(
                    select(ItemTag).where(ItemTag.item_id == iid, ItemTag.tag_id == tag.id)
                ).first()
                if not existing:
                    db.add(ItemTag(item_id=iid, tag_id=tag.id))
                    tag.usage_count += 1
                    db.add(tag)
        elif data.action == "enrich":
            _try_sync_enrich(item, db, current_user.id)
        processed += 1

    db.commit()
    return {"processed": processed, "total": len(data.item_ids)}


@router.post("/{item_id}/download-video")
def download_item_video(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download video for a YouTube/TikTok item."""
    item = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id, KnowledgeItem.user_id == current_user.id
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.source_platform not in (SourcePlatform.youtube, SourcePlatform.tiktok):
        raise HTTPException(
            status_code=400,
            detail="Video download only supported for YouTube and TikTok",
        )
    if not item.url:
        raise HTTPException(status_code=400, detail="No URL to download")

    from fourdpocket.config import get_settings

    settings = get_settings()
    output_dir = str(
        Path(settings.storage.base_path).expanduser()
        / str(current_user.id)
        / "videos"
    )

    from fourdpocket.workers.media_downloader import download_video
    video_path = download_video(item.url, output_dir)

    if not video_path:
        raise HTTPException(status_code=500, detail="Video download failed")

    media = list(item.media) if item.media else []
    media.append({"type": "video", "path": video_path})
    item.media = media
    db.add(item)
    db.commit()

    return {"status": "downloaded", "path": video_path}


@router.get("/{item_id}/media-proxy")
def media_proxy(
    item_id: uuid.UUID,
    url: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Proxy and cache images for an item (no auth required).
    Item IDs are UUIDs (unguessable). Fetches the URL server-side,
    caches locally, then serves from cache.
    Handles CORS-blocked and hotlink-protected URLs (e.g. LinkedIn).
    """
    import hashlib

    import httpx

    from fourdpocket.config import get_settings
    from fourdpocket.storage.local import LocalStorage

    item = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id,
            KnowledgeItem.user_id == current_user.id,
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not _is_safe_proxy_url(url):
        raise HTTPException(status_code=400, detail="URL not allowed")

    settings = get_settings()
    storage = LocalStorage(base_path=settings.storage.base_path)
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    uid = item.user_id
    # Extract extension from URL path only (not query/domain)
    from urllib.parse import urlparse as _urlparse
    _path = _urlparse(url).path
    _parts = _path.rsplit(".", 1)
    ext = _parts[-1].lower() if len(_parts) > 1 and len(_parts[-1]) <= 5 else "bin"
    filename = f"{item_id}_{url_hash}.{ext}"
    relative_path = f"{uid}/media/{filename}"

    # Check if already cached
    if storage.file_exists(relative_path):
        resolved = storage.get_absolute_path(relative_path)
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                    ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
                    ".mp4": "video/mp4", ".webm": "video/webm", ".pdf": "application/pdf"}
        import mimetypes
        mime_type = mime_map.get(resolved.suffix.lower()) or mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        return FileResponse(resolved, media_type=mime_type)

    # Fetch from source — validate each redirect hop for SSRF
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        current_fetch_url = url
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            for _hop in range(5):
                if not _is_safe_proxy_url(current_fetch_url):
                    raise HTTPException(status_code=400, detail="URL not allowed")
                resp = client.get(current_fetch_url, headers=headers)
                if resp.is_redirect:
                    current_fetch_url = resp.headers.get("location", "")
                    if not current_fetch_url:
                        raise HTTPException(status_code=502, detail="Empty redirect")
                    continue
                resp.raise_for_status()
                break
            else:
                raise HTTPException(status_code=502, detail="Too many redirects")
    except Exception as e:
        logger.warning("Media proxy fetch failed for %s: %s", url, e)
        raise HTTPException(status_code=502, detail="Failed to fetch image")

    # Detect correct extension from response content-type
    resp_ct = resp.headers.get("content-type", "").split(";")[0].strip()
    ct_ext_map = {
        "image/jpeg": "jpg", "image/png": "png", "image/gif": "gif",
        "image/webp": "webp", "image/svg+xml": "svg", "image/x-icon": "ico",
    }
    if resp_ct in ct_ext_map:
        ext = ct_ext_map[resp_ct]
        filename = f"{item_id}_{url_hash}.{ext}"

    # Save to local storage
    path = storage.save_file(uid, "media", filename, resp.content)

    # Update item media with local_path
    existing_media = list(item.media) if item.media else []
    # Find and update or append
    thumb_idx = next((i for i, m in enumerate(existing_media) if m.get("role") == "thumbnail" and m.get("url") == url), -1)
    if thumb_idx >= 0:
        existing_media[thumb_idx]["local_path"] = path
        existing_media[thumb_idx]["original_url"] = url
    else:
        existing_media.append({"type": "image", "url": url, "local_path": path, "role": "thumbnail"})
    item.media = existing_media
    db.add(item)
    db.commit()

    resolved = storage.get_absolute_path(path)
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
                ".mp4": "video/mp4", ".webm": "video/webm", ".pdf": "application/pdf"}
    import mimetypes as _mt
    mime_type = mime_map.get(resolved.suffix.lower()) or _mt.guess_type(str(resolved))[0] or "application/octet-stream"
    return FileResponse(resolved, media_type=mime_type)


@router.get("/{item_id}/media/{path:path}")
def serve_media(
    item_id: uuid.UUID,
    path: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """Serve locally-downloaded media files for an item."""
    from fastapi.responses import FileResponse

    item = db.exec(
        select(KnowledgeItem).where(
            KnowledgeItem.id == item_id, KnowledgeItem.user_id == current_user.id
        )
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    from fourdpocket.config import get_settings
    from fourdpocket.storage.local import LocalStorage

    settings = get_settings()
    storage = LocalStorage(base_path=settings.storage.base_path)

    # Ensure path belongs to the requesting user's directory (prevent cross-user access)
    user_prefix = str(current_user.id) + "/"
    if not path.startswith(user_prefix):
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        storage.get_file(path)  # Verify file exists
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Media not found")

    resolved = storage.get_absolute_path(path)
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".pdf": "application/pdf",
    }
    import mimetypes
    mime_type = mime_map.get(resolved.suffix.lower()) or mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"

    return FileResponse(resolved, media_type=mime_type)
