"""Share permission checks."""

import uuid
from datetime import datetime, timezone

from sqlmodel import Session, select

from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share, ShareRecipient, ShareRecipientRole
from fourdpocket.models.tag import ItemTag


def can_view_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
    """Check if user owns the item or has share access."""
    item = db.get(KnowledgeItem, item_id)
    if not item:
        return False
    if item.user_id == user_id:
        return True
    # Check if item is shared with user (skip expired shares)
    now = datetime.now(timezone.utc)
    shared = db.exec(
        select(ShareRecipient)
        .join(Share, Share.id == ShareRecipient.share_id)
        .where(
            Share.item_id == item_id,
            ShareRecipient.user_id == user_id,
            ShareRecipient.accepted,
            (Share.expires_at == None) | (Share.expires_at > now),  # noqa: E711
        )
    ).first()
    if shared:
        return True
    # Check if item is accessible via tag shares
    item_tags = db.exec(select(ItemTag).where(ItemTag.item_id == item_id)).all()
    for it in item_tags:
        tag_shared = db.exec(
            select(ShareRecipient)
            .join(Share, Share.id == ShareRecipient.share_id)
            .where(
                Share.tag_id == it.tag_id,
                ShareRecipient.user_id == user_id,
                ShareRecipient.accepted,
                (Share.expires_at == None) | (Share.expires_at > now),  # noqa: E711
            )
        ).first()
        if tag_shared:
            return True
    # Check if item is in any shared collection
    collection_items = db.exec(
        select(CollectionItem).where(CollectionItem.item_id == item_id)
    ).all()
    for ci in collection_items:
        if can_view_collection(db=db, user_id=user_id, collection_id=ci.collection_id):
            return True
    return False


def can_edit_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
    """Check if user owns the item or has editor share role."""
    item = db.get(KnowledgeItem, item_id)
    if not item:
        return False
    if item.user_id == user_id:
        return True
    now = datetime.now(timezone.utc)
    shared = db.exec(
        select(ShareRecipient)
        .join(Share, Share.id == ShareRecipient.share_id)
        .where(
            Share.item_id == item_id,
            ShareRecipient.user_id == user_id,
            ShareRecipient.role == ShareRecipientRole.editor,
            ShareRecipient.accepted,
            (Share.expires_at == None) | (Share.expires_at > now),  # noqa: E711
        )
    ).first()
    return shared is not None


def can_view_collection(
    db: Session, user_id: uuid.UUID, collection_id: uuid.UUID
) -> bool:
    """Check if user owns the collection or has share access."""
    col = db.get(Collection, collection_id)
    if not col:
        return False
    if col.user_id == user_id:
        return True
    now = datetime.now(timezone.utc)
    shared = db.exec(
        select(ShareRecipient)
        .join(Share, Share.id == ShareRecipient.share_id)
        .where(
            Share.collection_id == collection_id,
            ShareRecipient.user_id == user_id,
            ShareRecipient.accepted,
            (Share.expires_at == None) | (Share.expires_at > now),  # noqa: E711
        )
    ).first()
    return shared is not None
