"""Sharing API endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share, ShareRecipient, ShareRecipientRole, ShareType
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
    expires_hours: int | None = None


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


# Public link access — no authentication required

public_router = APIRouter(prefix="/public", tags=["sharing"])


@public_router.get("/{token}", response_model=PublicShareRead)
def get_public_share(
    token: str,
    db: Session = Depends(get_db),
):
    share = validate_public_token(db=db, token=token)
    if not share:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public share not found or expired",
        )
    return PublicShareRead(
        share_type=share.share_type,
        item_id=share.item_id,
        collection_id=share.collection_id,
        tag_id=share.tag_id,
        created_at=share.created_at,
    )
