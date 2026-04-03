"""RSS feed subscription endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.rss_feed import RSSFeed
from fourdpocket.models.user import User

router = APIRouter(prefix="/rss", tags=["rss"])


class RSSFeedCreate(BaseModel):
    url: str
    title: str | None = None
    category: str | None = None
    target_collection_id: str | None = None
    poll_interval: int = 3600


class RSSFeedUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    target_collection_id: str | None = None
    poll_interval: int | None = None
    is_active: bool | None = None


@router.get("")
def list_feeds(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.exec(select(RSSFeed).where(RSSFeed.user_id == current_user.id).order_by(RSSFeed.created_at.desc())).all()


@router.post("", status_code=201)
def create_feed(
    body: RSSFeedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feed = RSSFeed(
        user_id=current_user.id,
        url=body.url,
        title=body.title,
        category=body.category,
        target_collection_id=body.target_collection_id,
        poll_interval=body.poll_interval,
    )
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed


@router.patch("/{feed_id}")
def update_feed(
    feed_id: uuid.UUID,
    body: RSSFeedUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(feed, field, value)
    db.commit()
    db.refresh(feed)
    return feed


@router.delete("/{feed_id}", status_code=204)
def delete_feed(
    feed_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    db.delete(feed)
    db.commit()


@router.post("/{feed_id}/fetch")
def fetch_feed_now(
    feed_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually trigger a feed fetch."""
    feed = db.exec(select(RSSFeed).where(RSSFeed.id == feed_id, RSSFeed.user_id == current_user.id)).first()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    from fourdpocket.workers.rss_worker import fetch_rss_feed
    count = fetch_rss_feed(feed, db)
    return {"status": "fetched", "new_items": count}
