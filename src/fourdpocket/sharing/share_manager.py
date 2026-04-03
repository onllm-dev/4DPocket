"""Share management logic."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from fourdpocket.models.collection import Collection
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share, ShareRecipient, ShareRecipientRole, ShareType


def create_share(
    db: Session,
    owner_id: uuid.UUID,
    share_type: ShareType,
    item_id: uuid.UUID | None = None,
    collection_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    public: bool = False,
    expires_hours: int | None = None,
) -> Share:
    if item_id:
        item = db.get(KnowledgeItem, item_id)
        if not item or str(item.user_id) != str(owner_id):
            raise ValueError("Item not found or not owned by user")
    if collection_id:
        coll = db.get(Collection, collection_id)
        if not coll or str(coll.user_id) != str(owner_id):
            raise ValueError("Collection not found or not owned by user")

    share = Share(
        owner_id=owner_id,
        share_type=share_type,
        item_id=item_id,
        collection_id=collection_id,
        tag_id=tag_id,
    )
    if public:
        share.public_token = secrets.token_urlsafe(32)
    if expires_hours:
        share.expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def add_recipient(
    db: Session,
    share_id: uuid.UUID,
    user_id: uuid.UUID,
    role: ShareRecipientRole = ShareRecipientRole.viewer,
) -> ShareRecipient:
    existing = db.exec(
        select(ShareRecipient).where(
            ShareRecipient.share_id == share_id,
            ShareRecipient.user_id == user_id,
        )
    ).first()
    if existing:
        return existing

    recipient = ShareRecipient(
        share_id=share_id,
        user_id=user_id,
        role=role,
        accepted=False,
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return recipient


def revoke_share(db: Session, share_id: uuid.UUID, owner_id: uuid.UUID) -> bool:
    share = db.get(Share, share_id)
    if not share or share.owner_id != owner_id:
        return False
    # Delete recipients
    recipients = db.exec(
        select(ShareRecipient).where(ShareRecipient.share_id == share_id)
    ).all()
    for r in recipients:
        db.delete(r)
    db.delete(share)
    db.commit()
    return True


def validate_public_token(db: Session, token: str) -> Share | None:
    share = db.exec(select(Share).where(Share.public_token == token)).first()
    if not share:
        return None
    if share.expires_at and share.expires_at < datetime.now(timezone.utc):
        return None
    return share
