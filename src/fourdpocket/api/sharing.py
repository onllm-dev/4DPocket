"""Sharing API endpoints."""

import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share, ShareRecipient, ShareRecipientRole, ShareType
from fourdpocket.models.tag import ItemTag, Tag
from fourdpocket.models.user import User
from fourdpocket.sharing.share_manager import (
    add_recipient,
    create_share,
    revoke_share,
    validate_public_token,
)

router = APIRouter(prefix="/shares", tags=["sharing"])


# --- Schemas ---


class ShareCreate(BaseModel):
    share_type: ShareType
    item_id: uuid.UUID | None = None
    collection_id: uuid.UUID | None = None
    tag_id: uuid.UUID | None = None
    public: bool = False
    expires_hours: int | None = Field(default=None, ge=1, le=8760)  # 1 hour to 1 year
    recipient_email: str | None = None
    permission: str = "viewer"  # "viewer" or "editor"


class ShareRead(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    share_type: ShareType
    item_id: uuid.UUID | None
    collection_id: uuid.UUID | None
    tag_id: uuid.UUID | None
    public_token: str | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RecipientAdd(BaseModel):
    user_id: uuid.UUID
    role: ShareRecipientRole = ShareRecipientRole.viewer


class RecipientRead(BaseModel):
    id: uuid.UUID
    share_id: uuid.UUID
    user_id: uuid.UUID
    role: ShareRecipientRole
    accepted: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SharedItemRead(BaseModel):
    share_id: uuid.UUID
    share_type: ShareType
    item_id: uuid.UUID | None
    collection_id: uuid.UUID | None
    tag_id: uuid.UUID | None
    role: ShareRecipientRole
    accepted: bool
    owner_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class PublicShareRead(BaseModel):
    share_type: ShareType
    item_id: uuid.UUID | None
    collection_id: uuid.UUID | None
    tag_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Endpoints ---


@router.post("", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
def create_share_endpoint(
    body: ShareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        share = create_share(
            db=db,
            owner_id=current_user.id,
            share_type=body.share_type,
            item_id=body.item_id,
            collection_id=body.collection_id,
            tag_id=body.tag_id,
            public=body.public,
            expires_hours=body.expires_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    if body.recipient_email:
        recipient_user = db.exec(
            select(User).where(User.email == body.recipient_email)
        ).first()
        if not recipient_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if recipient_user.id == current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot share with yourself")
        existing = db.exec(
            select(ShareRecipient).where(
                ShareRecipient.share_id == share.id,
                ShareRecipient.user_id == recipient_user.id,
            )
        ).first()
        if not existing:
            role = ShareRecipientRole.editor if body.permission == "editor" else ShareRecipientRole.viewer
            sr = ShareRecipient(
                share_id=share.id,
                user_id=recipient_user.id,
                role=role,
            )
            db.add(sr)
            db.commit()

    return share


@router.get("", response_model=list[ShareRead])
def list_shares(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    shares = db.exec(
        select(Share)
        .where(Share.owner_id == current_user.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return shares


@router.delete("/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share_endpoint(
    share_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = revoke_share(db=db, share_id=share_id, owner_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Share not found"
        )


@router.post(
    "/{share_id}/recipients",
    response_model=RecipientRead,
    status_code=status.HTTP_201_CREATED,
)
def add_recipient_endpoint(
    share_id: uuid.UUID,
    body: RecipientAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    share = db.get(Share, share_id)
    if not share or share.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Share not found"
        )
    recipient = add_recipient(
        db=db, share_id=share_id, user_id=body.user_id, role=body.role
    )
    return recipient


@router.delete(
    "/{share_id}/recipients/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_recipient_endpoint(
    share_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    share = db.get(Share, share_id)
    if not share or share.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Share not found"
        )
    recipient = db.exec(
        select(ShareRecipient).where(
            ShareRecipient.share_id == share_id,
            ShareRecipient.user_id == user_id,
        )
    ).first()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recipient not found"
        )
    db.delete(recipient)
    db.commit()


@router.get("/shared-with-me", response_model=list[SharedItemRead])
def list_shared_with_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    results = db.exec(
        select(ShareRecipient)
        .where(ShareRecipient.user_id == current_user.id)
        .offset(offset)
        .limit(limit)
    ).all()

    items: list[SharedItemRead] = []
    for r in results:
        share = db.get(Share, r.share_id)
        if not share:
            continue
        items.append(
            SharedItemRead(
                share_id=share.id,
                share_type=share.share_type,
                item_id=share.item_id,
                collection_id=share.collection_id,
                tag_id=share.tag_id,
                role=r.role,
                accepted=r.accepted,
                owner_id=share.owner_id,
                created_at=r.created_at,
            )
        )
    return items


@router.post("/{share_id}/accept", response_model=RecipientRead)
def accept_share(
    share_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipient = db.exec(
        select(ShareRecipient).where(
            ShareRecipient.share_id == share_id,
            ShareRecipient.user_id == current_user.id,
        )
    ).first()
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Share invitation not found"
        )
    recipient.accepted = True
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return recipient


@router.get("/history")
def share_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get sharing history - what you've shared with whom."""
    shares = db.exec(
        select(Share).where(Share.owner_id == current_user.id).order_by(Share.created_at.desc())
    ).all()

    history = []
    for share in shares:
        recipients = db.exec(
            select(ShareRecipient).where(ShareRecipient.share_id == share.id)
        ).all()

        # Get item/collection title
        title = "Unknown"
        if share.item_id:
            item = db.get(KnowledgeItem, share.item_id)
            title = item.title if item else "Deleted item"
        elif share.collection_id:
            from fourdpocket.models.collection import Collection
            coll = db.get(Collection, share.collection_id)
            title = coll.name if coll else "Deleted collection"

        recipient_info = []
        for r in recipients:
            u = db.get(User, r.user_id)
            recipient_info.append({
                "user_id": str(r.user_id),
                "display_name": u.display_name or u.username if u else "Unknown",
                "role": r.role,
                "accepted": r.accepted,
            })

        history.append({
            "share_id": str(share.id),
            "share_type": share.share_type,
            "title": title,
            "has_public_link": share.public_token is not None,
            "recipients": recipient_info,
            "created_at": share.created_at.isoformat() if share.created_at else None,
        })

    return history


# Public link access - no authentication required

public_router = APIRouter(prefix="/public", tags=["sharing"])

_public_token_attempts: dict[str, dict] = {}


def _check_public_rate_limit(client_ip: str) -> None:
    """Rate limit public token access with exponential backoff per IP."""
    now = time.time()
    state = _public_token_attempts.get(client_ip, {"attempts": [], "backoff_until": 0.0, "failures": 0})
    if state["backoff_until"] > now:
        remaining = int(state["backoff_until"] - now)
        raise HTTPException(429, f"Too many attempts. Try again in {remaining} seconds.")
    state["attempts"] = [t for t in state["attempts"] if now - t < 60]
    if len(state["attempts"]) >= 5:
        state["failures"] = min(state["failures"] + 1, 5)
        backoff_seconds = 60 * (2 ** (state["failures"] - 1))  # 1, 2, 4, 8, 16 min
        state["backoff_until"] = now + backoff_seconds
        _public_token_attempts[client_ip] = state
        raise HTTPException(429, f"Too many attempts. Try again in {backoff_seconds} seconds.")
    state["attempts"].append(now)
    _public_token_attempts[client_ip] = state


@public_router.get("/{token}")
def get_public_share(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
):
    client_ip = request.client.host if request.client else "unknown"
    _check_public_rate_limit(client_ip)
    share = validate_public_token(db=db, token=token)
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public share not found or expired",
        )
    if share.item_id:
        item = db.get(KnowledgeItem, share.item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared item not found")
        tag_links = db.exec(select(ItemTag).where(ItemTag.item_id == item.id)).all()
        tag_ids = [tl.tag_id for tl in tag_links]
        tags = db.exec(select(Tag).where(Tag.id.in_(tag_ids))).all() if tag_ids else []
        owner = db.get(User, item.user_id)
        return {
            "id": str(item.id),
            "title": item.title,
            "url": item.url,
            "description": item.description,
            "content": item.content,
            "summary": item.summary,
            "source_platform": item.source_platform,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "tags": [t.name for t in tags],
            "owner_display_name": owner.display_name or owner.username if owner else "Unknown",
        }
    return PublicShareRead(
        share_type=share.share_type,
        item_id=share.item_id,
        collection_id=share.collection_id,
        tag_id=share.tag_id,
        created_at=share.created_at,
    )
