"""Personal Access Token management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, col, select

from fourdpocket.api.api_token_utils import (
    compute_expiry,
    generate_token,
)
from fourdpocket.api.deps import get_current_user, get_db, require_jwt_session
from fourdpocket.models.api_token import ApiToken, ApiTokenCollection
from fourdpocket.models.base import ApiTokenRole, UserRole
from fourdpocket.models.collection import Collection
from fourdpocket.models.user import User

router = APIRouter(prefix="/auth/tokens", tags=["auth"])


# ─── Schemas ──────────────────────────────────────────────────

VALID_EXPIRY_DAYS = {None, 30, 90, 365, 730}


class CreateTokenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: ApiTokenRole = ApiTokenRole.viewer
    all_collections: bool = True
    collection_ids: list[uuid.UUID] = Field(default_factory=list)
    include_uncollected: bool = True
    allow_deletion: bool = False
    admin_scope: bool = False
    expires_in_days: int | None = None

    @field_validator("expires_in_days")
    @classmethod
    def valid_expiry(cls, v: int | None) -> int | None:
        if v not in VALID_EXPIRY_DAYS:
            raise ValueError(
                "expires_in_days must be one of: null (no expiry), 30, 90, 365, 730"
            )
        return v


class TokenRead(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    role: ApiTokenRole
    all_collections: bool
    collection_ids: list[uuid.UUID]
    include_uncollected: bool
    allow_deletion: bool
    admin_scope: bool
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class TokenCreateResponse(TokenRead):
    token: str = Field(description="Plaintext token — shown ONCE. Store securely.")


# ─── Helpers ──────────────────────────────────────────────────


def _token_collection_ids(db: Session, token_id: uuid.UUID) -> list[uuid.UUID]:
    rows = db.exec(
        select(ApiTokenCollection.collection_id).where(
            ApiTokenCollection.token_id == token_id
        )
    ).all()
    return list(rows)


def _to_read(db: Session, token: ApiToken) -> TokenRead:
    return TokenRead(
        id=token.id,
        name=token.name,
        prefix=token.token_prefix,
        role=token.role,
        all_collections=token.all_collections,
        collection_ids=_token_collection_ids(db, token.id),
        include_uncollected=token.include_uncollected,
        allow_deletion=token.allow_deletion,
        admin_scope=token.admin_scope,
        created_at=token.created_at,
        expires_at=token.expires_at,
        last_used_at=token.last_used_at,
        revoked_at=token.revoked_at,
    )


# ─── Endpoints ────────────────────────────────────────────────


@router.post("", response_model=TokenCreateResponse, status_code=status.HTTP_201_CREATED)
def create_token(
    data: CreateTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_jwt_session),
):
    """Create a new PAT. Returns the plaintext token exactly once."""
    # Only admins may mint admin-scoped tokens.
    if data.admin_scope and current_user.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can create tokens with admin_scope.",
        )

    # Validate the collection ids belong to the requester when provided.
    if not data.all_collections:
        if not data.collection_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide collection_ids or set all_collections=true.",
            )
        found = db.exec(
            select(Collection).where(
                Collection.id.in_(data.collection_ids),
                Collection.user_id == current_user.id,
            )
        ).all()
        if len(found) != len(set(data.collection_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more collection_ids are invalid.",
            )

    generated = generate_token()
    token = ApiToken(
        user_id=current_user.id,
        name=data.name.strip(),
        token_prefix=generated.prefix,
        token_hash=generated.token_hash,
        role=data.role,
        all_collections=data.all_collections,
        include_uncollected=data.include_uncollected,
        allow_deletion=data.allow_deletion,
        admin_scope=data.admin_scope,
        expires_at=compute_expiry(data.expires_in_days),
    )
    db.add(token)
    db.commit()
    db.refresh(token)

    if not data.all_collections:
        for cid in set(data.collection_ids):
            db.add(ApiTokenCollection(token_id=token.id, collection_id=cid))
        db.commit()

    read = _to_read(db, token)
    return TokenCreateResponse(**read.model_dump(), token=generated.plaintext)


@router.get("", response_model=list[TokenRead])
def list_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's tokens (metadata only; no plaintext ever returned)."""
    rows = db.exec(
        select(ApiToken)
        .where(ApiToken.user_id == current_user.id)
        .order_by(col(ApiToken.created_at).desc())
    ).all()
    return [_to_read(db, t) for t in rows]


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(
    token_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_jwt_session),
):
    """Revoke a token by id. Idempotent — already-revoked tokens stay revoked."""
    token = db.get(ApiToken, token_id)
    if token is None or token.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Token not found"
        )
    if token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        db.add(token)
        db.commit()
    return None


@router.post("/revoke-all", status_code=status.HTTP_204_NO_CONTENT)
def revoke_all_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_jwt_session),
):
    """Revoke every active token belonging to the current user (big red button)."""
    now = datetime.now(timezone.utc)
    rows = db.exec(
        select(ApiToken).where(
            ApiToken.user_id == current_user.id,
            ApiToken.revoked_at.is_(None),
        )
    ).all()
    for t in rows:
        t.revoked_at = now
        db.add(t)
    db.commit()
    return None
