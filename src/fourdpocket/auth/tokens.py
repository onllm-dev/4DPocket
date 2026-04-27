"""Token generation and verification helpers for password reset and email verification.

These are short-lived single-use DB tokens — separate from JWTs.
"""

import hashlib
import secrets
from datetime import datetime, timezone

from fourdpocket.models.email_verification import EmailVerificationToken
from fourdpocket.models.password_reset import PasswordResetToken


def generate_token() -> tuple[str, str]:
    """Generate a new opaque token.

    Returns (raw_token, sha256_hash). The raw token is returned to the user
    once (in an email link). Only the hash is stored in the database.
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    """Return the SHA-256 hex digest of a raw token string."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_expired(token: PasswordResetToken | EmailVerificationToken) -> bool:
    """Return True if the token's expires_at is in the past."""
    now = datetime.now(timezone.utc)
    expires = token.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return now >= expires
