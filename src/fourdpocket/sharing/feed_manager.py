"""Knowledge feed subscription logic."""

import uuid

from sqlmodel import Session, col, select

from fourdpocket.models.feed import KnowledgeFeed
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share


def subscribe(
    db: Session, subscriber_id: uuid.UUID, publisher_id: uuid.UUID
) -> KnowledgeFeed:
    existing = db.exec(
        select(KnowledgeFeed).where(
            KnowledgeFeed.subscriber_id == subscriber_id,
            KnowledgeFeed.publisher_id == publisher_id,
        )
    ).first()
    if existing:
        return existing

    feed = KnowledgeFeed(subscriber_id=subscriber_id, publisher_id=publisher_id)
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed


def unsubscribe(
    db: Session, subscriber_id: uuid.UUID, publisher_id: uuid.UUID
) -> bool:
    feed = db.exec(
        select(KnowledgeFeed).where(
            KnowledgeFeed.subscriber_id == subscriber_id,
            KnowledgeFeed.publisher_id == publisher_id,
        )
    ).first()
    if not feed:
        return False
    db.delete(feed)
    db.commit()
    return True


def get_feed_items(
    db: Session, subscriber_id: uuid.UUID, limit: int = 20, offset: int = 0
) -> list[KnowledgeItem]:
    """Get items from users the subscriber follows."""
    publisher_ids = db.exec(
        select(KnowledgeFeed.publisher_id).where(
            KnowledgeFeed.subscriber_id == subscriber_id
        )
    ).all()

    if not publisher_ids:
        return []

    public_item_ids = select(Share.item_id).where(
        Share.owner_id.in_(publisher_ids),
        Share.item_id.is_not(None),
        Share.public_token.is_not(None),
    )

    items = db.exec(
        select(KnowledgeItem)
        .where(
            KnowledgeItem.user_id.in_(publisher_ids),
            KnowledgeItem.is_archived == False,
            KnowledgeItem.id.in_(public_item_ids),
        )
        .order_by(col(KnowledgeItem.created_at).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return items
