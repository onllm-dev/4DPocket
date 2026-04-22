"""Personal Access Token (PAT) utilities.

Token format: ``fdp_pat_<6char-id>_<43char-secret>``.

The 6-character id is the public lookup key (indexed, unique). The secret
portion is compared against ``sha256(full_token)`` using
``hmac.compare_digest`` to resist timing attacks. Only the hash is persisted —
plaintext is returned to the user exactly once at creation.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from fourdpocket.models.api_token import ApiToken, ApiTokenCollection
from fourdpocket.models.base import ApiTokenRole
from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.user import User

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "fdp_pat_"
_ID_LENGTH = 8  # hex chars; ``_`` is our separator so prefix must avoid it
_SECRET_BYTES = 32  # 32 bytes → 43 urlsafe base64 chars

# Dummy hash used for constant-time padding when prefix lookup misses.
# Value intentionally cannot collide with any real sha256(token).
_DUMMY_HASH = "0" * 64

# Minimum interval between last_used_at updates per token to avoid write amplification.
_LAST_USED_DEBOUNCE = timedelta(minutes=1)


@dataclass
class GeneratedToken:
    plaintext: str
    prefix: str
    token_hash: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_token() -> GeneratedToken:
    """Generate a new token plaintext and its storable hash.

    The prefix is hex (0-9a-f) so it cannot contain the ``_`` separator —
    previous urlsafe-base64 prefixes occasionally included ``_`` or ``-``,
    which broke ``_parse_prefix`` when splitting on the first underscore.
    """
    prefix = secrets.token_hex(_ID_LENGTH // 2)
    secret = secrets.token_urlsafe(_SECRET_BYTES)
    plaintext = f"{TOKEN_PREFIX}{prefix}_{secret}"
    token_hash = _hash(plaintext)
    return GeneratedToken(plaintext=plaintext, prefix=prefix, token_hash=token_hash)


def _hash(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def looks_like_pat(token: str | None) -> bool:
    return bool(token) and token.startswith(TOKEN_PREFIX)


def _parse_prefix(plaintext: str) -> str | None:
    """Extract the lookup prefix from a well-formed token, or None if malformed."""
    if not looks_like_pat(plaintext):
        return None
    body = plaintext[len(TOKEN_PREFIX):]
    parts = body.split("_", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0]


def resolve_token(db: Session, plaintext: str) -> ApiToken | None:
    """Look up a token by plaintext. Returns the ``ApiToken`` row if valid.

    Valid means: found by prefix, hash matches, not revoked, not expired, owner
    active. Constant-time comparison on hash; dummy compare when prefix misses
    so timing cannot leak whether a prefix is registered.
    """
    prefix = _parse_prefix(plaintext)
    if prefix is None:
        hmac.compare_digest(_DUMMY_HASH, _DUMMY_HASH)
        return None

    token_row = db.exec(select(ApiToken).where(ApiToken.token_prefix == prefix)).first()
    computed = _hash(plaintext)

    if token_row is None:
        hmac.compare_digest(computed, _DUMMY_HASH)
        return None

    if not hmac.compare_digest(computed, token_row.token_hash):
        return None

    if token_row.revoked_at is not None:
        return None

    now = _utcnow()
    if token_row.expires_at is not None:
        expires = token_row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            return None

    user = db.get(User, token_row.user_id)
    if user is None or user.is_active is False:
        return None

    return token_row


def touch_last_used(db: Session, token: ApiToken) -> None:
    """Update ``last_used_at`` at most once per minute to avoid write amplification."""
    now = _utcnow()
    last = token.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    if last is not None and (now - last) < _LAST_USED_DEBOUNCE:
        return
    token.last_used_at = now
    db.add(token)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to touch PAT last_used_at: %s", exc)


def compute_expiry(days: int | None) -> datetime | None:
    """Convert a days-from-now value to an absolute expiry. ``None`` = no expiry."""
    if days is None or days <= 0:
        return None
    return _utcnow() + timedelta(days=days)


def token_can_access_collection(
    db: Session, token: ApiToken, collection_id: uuid.UUID
) -> bool:
    """Does this PAT have access to the given collection?"""
    if token.all_collections:
        return True
    link = db.exec(
        select(ApiTokenCollection).where(
            ApiTokenCollection.token_id == token.id,
            ApiTokenCollection.collection_id == collection_id,
        )
    ).first()
    return link is not None


def token_allowed_collection_ids(db: Session, token: ApiToken) -> list[uuid.UUID] | None:
    """Return the list of collection ids the token may access.

    ``None`` means ``all_collections`` — caller should skip filtering.
    """
    if token.all_collections:
        return None
    rows = db.exec(
        select(ApiTokenCollection.collection_id).where(
            ApiTokenCollection.token_id == token.id
        )
    ).all()
    return [r for r in rows]


def token_allowed_item_ids(
    db: Session, token: ApiToken, user_id: uuid.UUID
) -> set[uuid.UUID] | None:
    """Compute the set of item ids a collection-scoped token may see.

    Returns ``None`` for all_collections tokens (no filtering needed).
    Includes uncollected items when ``token.include_uncollected`` is set.
    """
    if token.all_collections:
        return None

    allowed_collections = token_allowed_collection_ids(db, token) or []
    item_ids: set[uuid.UUID] = set()

    if allowed_collections:
        rows = db.exec(
            select(CollectionItem.item_id).where(
                CollectionItem.collection_id.in_(allowed_collections)
            )
        ).all()
        item_ids.update(rows)

    if token.include_uncollected:
        from fourdpocket.models.item import KnowledgeItem

        all_user_items = db.exec(
            select(KnowledgeItem.id).where(KnowledgeItem.user_id == user_id)
        ).all()
        collected = db.exec(
            select(CollectionItem.item_id)
            .join(Collection, Collection.id == CollectionItem.collection_id)
            .where(Collection.user_id == user_id)
        ).all()
        uncollected = set(all_user_items) - set(collected)
        item_ids.update(uncollected)

    return item_ids


def token_can_access_item(
    db: Session, token: ApiToken, item_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Does this PAT cover the given item id?"""
    allowed = token_allowed_item_ids(db, token, user_id)
    if allowed is None:
        return True
    return item_id in allowed


def require_editor(token: ApiToken) -> None:
    """Raise HTTP 403 if the token is not an editor."""
    from fastapi import HTTPException, status

    if token.role != ApiTokenRole.editor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation requires an editor-role token.",
        )


def require_deletion(token: ApiToken) -> None:
    """Raise HTTP 403 if the token is not allowed to delete."""
    from fastapi import HTTPException, status

    require_editor(token)
    if not token.allow_deletion:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not have allow_deletion enabled.",
        )


def require_admin_scope(token: ApiToken) -> None:
    """Raise HTTP 403 if the token does not have admin scope."""
    from fastapi import HTTPException, status

    if not token.admin_scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin operations require a token with admin_scope.",
        )
