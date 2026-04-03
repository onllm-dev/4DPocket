"""Share permission checks."""

import uuid

from sqlmodel import Session, select

from fourdpocket.models.collection import Collection
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share, ShareRecipient, ShareRecipientRole


def can_view_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
    """Check if user owns the item or has share access."""
    item = db.get(KnowledgeItem, item_id)
    if not item:
        return False
    if item.user_id == user_id:
        return True
    # Check if item is shared with user
    shared = db.exec(
        select(ShareRecipient)
        .join(Share, Share.id == ShareRecipient.share_id)
        .where(
            Share.item_id == item_id,
            ShareRecipient.user_id == user_id,
            ShareRecipient.accepted,
        )
    ).first()
    if shared:
        return True
    # Check if item's collection is shared
    # (items in a shared collection are accessible)
    return False


def can_edit_item(db: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> bool:
    """Check if user owns the item or has editor share role."""
    item = db.get(KnowledgeItem, item_id)
    if not item:
        return False
    if item.user_id == user_id:
        return True
    shared = db.exec(
        select(ShareRecipient)
        .join(Share, Share.id == ShareRecipient.share_id)
        .where(
            Share.item_id == item_id,
            ShareRecipient.user_id == user_id,
            ShareRecipient.role == ShareRecipientRole.editor,
            ShareRecipient.accepted,
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
    shared = db.exec(
        select(ShareRecipient)
        .join(Share, Share.id == ShareRecipient.share_id)
        .where(
            Share.collection_id == collection_id,
            ShareRecipient.user_id == user_id,
            ShareRecipient.accepted,
        )
    ).first()
    return shared is not None
