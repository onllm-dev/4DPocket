"""RSS feed subscription endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db, require_pat_editor
from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.feed_entry import FeedEntry, FeedEntryRead
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.rss_feed import RSSFeed
from fourdpocket.models.user import User
from fourdpocket.utils.ssrf import is_safe_url

router = APIRouter(prefix="/rss", tags=["rss"])


class RSSFeedCreate(BaseModel):
    url: str
    title: str | None = None
    category: str | None = None
    target_collection_id: uuid.UUID | None = None
    poll_interval: int = 3600
    format: str = "rss"
    mode: str = "auto"
    filters: str | None = None


class RSSFeedUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    target_collection_id: uuid.UUID | None = None
    poll_interval: int | None = None
    is_active: bool | None = None


@router.get("")
def list_feeds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.exec(select(RSSFeed).where(RSSFeed.user_id == current_user.id).order_by(RSSFeed.created_at.desc())).all()


def _is_safe_feed_url(url: str) -> bool:
    """Validate RSS feed URL is safe (SSRF protection at creation time)."""
    return is_safe_url(url)


def _validate_collection_ownership(
    db: Session, collection_id: uuid.UUID | None, user_id: uuid.UUID
) -> None:
    """Raise 404 if collection_id is set but does not belong to user_id."""
    if collection_id is None:
        return
    col = db.exec(
        select(Collection).where(Collection.id == collection_id, Collection.user_id == user_id)
    ).first()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")


@router.post("", status_code=201)
def create_feed(
    body: RSSFeedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    if not _is_safe_feed_url(body.url):
        raise HTTPException(status_code=400, detail="Feed URL targets a blocked network")
    _validate_collection_ownership(db, body.target_collection_id, current_user.id)

    feed = RSSFeed(
        user_id=current_user.id,
        url=body.url,
        title=body.title,
        category=body.category,
        target_collection_id=body.target_collection_id,
        poll_interval=body.poll_interval,
        format=body.format,
        mode=body.mode,
        filters=body.filters,
    )
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed


_UPDATE_FEED_ALLOWLIST = {"title", "category", "poll_interval", "is_active", "target_collection_id"}


@router.patch("/{feed_id}")
def update_feed(
    feed_id: uuid.UUID,
    body: RSSFeedUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _UPDATE_FEED_ALLOWLIST}
    if "target_collection_id" in updates:
        _validate_collection_ownership(db, updates["target_collection_id"], current_user.id)
    for field, value in updates.items():
        setattr(feed, field, value)
    db.commit()
    db.refresh(feed)
    return feed


@router.delete("/{feed_id}", status_code=204)
def delete_feed(
    feed_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    # Cascade: remove feed entries
    for entry in db.exec(select(FeedEntry).where(FeedEntry.feed_id == feed_id)).all():
        db.delete(entry)
    db.delete(feed)
    db.commit()


@router.post("/{feed_id}/fetch")
def fetch_feed_now(
    feed_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    """Manually trigger a feed fetch."""
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    from fourdpocket.workers.rss_worker import fetch_rss_feed
    count = fetch_rss_feed(feed, db)
    return {"status": "fetched", "new_items": count}


@router.get("/{feed_id}/entries", response_model=list[FeedEntryRead])
def list_feed_entries(
    feed_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: str | None = None,
):
    """List feed entries, optionally filtered by status."""
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    query = select(FeedEntry).where(
        FeedEntry.feed_id == feed_id,
        FeedEntry.user_id == current_user.id,
    )
    if status_filter:
        query = query.where(FeedEntry.status == status_filter)
    query = query.order_by(FeedEntry.created_at.desc())
    return db.exec(query).all()


class EntryStatusUpdate(BaseModel):
    status: str  # approved, rejected


@router.post("/{feed_id}/entries/{entry_id}/approve")
def approve_feed_entry(
    feed_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    """Approve a feed entry: create a KnowledgeItem from entry data."""
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    entry = db.exec(
        select(FeedEntry).where(
            FeedEntry.id == entry_id,
            FeedEntry.feed_id == feed_id,
            FeedEntry.user_id == current_user.id,
        )
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Create KnowledgeItem from entry
    item = KnowledgeItem(
        user_id=current_user.id,
        url=entry.url,
        title=entry.title,
        description=entry.content_snippet,
    )
    db.add(item)

    # Add to target collection if set — re-verify ownership in case collection changed since feed creation
    if feed.target_collection_id:
        col = db.exec(
            select(Collection).where(
                Collection.id == feed.target_collection_id,
                Collection.user_id == current_user.id,
            )
        ).first()
        if col:
            link = CollectionItem(
                collection_id=feed.target_collection_id,
                item_id=item.id,
                position=0,
            )
            db.add(link)

    entry.status = "approved"
    db.add(entry)
    db.commit()
    db.refresh(item)

    return {"status": "approved", "item_id": str(item.id)}


@router.patch("/{feed_id}/entries/{entry_id}")
def update_feed_entry_status(
    feed_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: EntryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_pat_editor),
):
    """Update a feed entry status (approve/reject)."""
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")

    entry = db.exec(
        select(FeedEntry).where(
            FeedEntry.id == entry_id,
            FeedEntry.feed_id == feed_id,
            FeedEntry.user_id == current_user.id,
        )
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if body.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")

    entry.status = body.status
    db.add(entry)
    db.commit()
    return {"status": entry.status, "entry_id": str(entry.id)}
