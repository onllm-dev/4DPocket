"""Knowledge item CRUD endpoints."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, col, select
from sqlmodel import delete as sql_delete

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.base import ItemType, SourcePlatform
from fourdpocket.models.item import ItemCreate, ItemRead, ItemUpdate, KnowledgeItem
from fourdpocket.models.tag import ItemTag, Tag
from fourdpocket.models.user import User

router = APIRouter(prefix="/items", tags=["items"])


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
                detail={"message": "You already saved this URL", "existing_id": str(existing.id)},
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
        from fourdpocket.search.indexer import SearchIndexer

        indexer = SearchIndexer(db)
        indexer.index_item(item)
    except Exception:
        pass  # Search indexing is best-effort

    # Run automation rules
    try:
        from fourdpocket.workers.rule_engine import run_rules_for_item

        run_rules_for_item(item, db)
    except Exception:
        pass  # Rules are best-effort

    # Dispatch background processing workers
    try:
        if item.url:
            from fourdpocket.workers.fetcher import fetch_and_process_url
            from fourdpocket.workers.screenshot import capture_screenshot
            fetch_and_process_url(str(item.id), item.url, str(current_user.id))
            capture_screenshot(str(item.id), item.url, str(current_user.id))
        else:
            from fourdpocket.workers.ai_enrichment import enrich_item
            enrich_item(str(item.id), str(current_user.id))
    except Exception:
        pass  # Worker dispatch is best-effort

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
    return items


@router.get("/{item_id}", response_model=ItemRead)
def get_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


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


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(KnowledgeItem, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")

    # Delete associated tags
    tags = db.exec(select(ItemTag).where(ItemTag.item_id == item_id)).all()
    for tag_link in tags:
        db.delete(tag_link)

    db.delete(item)
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


@router.get("/timeline")
def get_timeline(
    days: int = Query(default=30, ge=1, le=365),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
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


@router.patch("/{item_id}/reading-progress")
def update_reading_progress(
    item_id: uuid.UUID,
    body: dict,  # {"progress": 0-100}
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
    progress = max(0, min(100, body.get("progress", 0)))
    item.reading_progress = progress
    db.commit()
    return {"status": "updated", "reading_progress": progress}


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
            db.exec(sql_delete(ItemTag).where(ItemTag.item_id == item.id))
            db.delete(item)
        elif data.action == "favorite":
            item.is_favorite = True
            db.add(item)
        elif data.action == "unfavorite":
            item.is_favorite = False
            db.add(item)
        elif data.action == "tag" and data.tag_id:
            tag = db.get(Tag, data.tag_id)
            if tag and tag.user_id == current_user.id:
                existing = db.exec(
                    select(ItemTag).where(ItemTag.item_id == iid, ItemTag.tag_id == data.tag_id)
                ).first()
                if not existing:
                    db.add(ItemTag(item_id=iid, tag_id=data.tag_id))
                    tag.usage_count += 1
                    db.add(tag)
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
