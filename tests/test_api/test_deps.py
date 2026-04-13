"""Security tests for api/deps.py identity resolution."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
import pytest
from sqlmodel import Session, select

from fourdpocket.api.auth_utils import create_access_token, hash_password
from fourdpocket.api.deps import _resolve_identity, require_admin
from fourdpocket.config import get_settings
from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.base import ApiTokenRole, UserRole
from fourdpocket.models.user import User

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

class _State:
    """Simple stand-in for request.state that supports attribute assignment."""
    def __init__(self):
        self._attrs: dict = {}

    def __setattr__(self, name, value):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            self._attrs[name] = value

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._attrs.get(name)


def _mock_request():
    """Return a mock Request with a state that supports .pat = ... assignment."""
    req = MagicMock()
    req.state = _State()
    return req


def _jwt_token(user_id: uuid.UUID) -> str:
    """Encode a short-lived JWT for the given user id."""
    return create_access_token(user_id)


# ---------------------------------------------------------------------------
# Single-user mode
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_single_user_mode_auto_admin_creates_user(db: Session):
    """In single-user mode with no admin, one is auto-created on first request."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "single"

    try:
        # Ensure no admin exists
        admin = db.exec(select(User).where(User.role == UserRole.admin)).first()
        if admin:
            db.delete(admin)
            db.commit()

        req = _mock_request()
        user, pat = _resolve_identity(req, token=None, db=db)

        assert user.role == UserRole.admin
        assert user.email.startswith("admin-")
        assert pat is None
    finally:
        settings.auth.mode = original


@pytest.mark.security
def test_single_user_mode_no_token_returns_existing_admin(db: Session):
    """Single-user mode with no token returns the existing admin (no 401)."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "single"

    try:
        # Ensure admin exists
        existing = db.exec(select(User).where(User.role == UserRole.admin)).first()
        if not existing:
            existing = User(
                email="existing@single.local",
                username="admin",
                password_hash=hash_password("AnyPass123!"),
                display_name="Single Admin",
                role=UserRole.admin,
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)

        req = _mock_request()
        user, pat = _resolve_identity(req, token=None, db=db)

        assert user.id == existing.id
        assert pat is None
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# Missing token (multi-user mode)
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_missing_token_raises_401_multi_user_mode(db: Session):
    """Multi-user mode with no token at all returns 401."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    try:
        req = _mock_request()
        with pytest.raises(__import__("fastapi").HTTPException) as exc_info:
            _resolve_identity(req, token=None, db=db)

        assert exc_info.value.status_code == 401
        assert "Not authenticated" in exc_info.value.detail
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# PAT routing — valid
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_pat_valid_token_returns_user_and_pat(db: Session):
    """A well-formed fdp_pat_... token that resolves successfully returns user+pat."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    user = User(
        email="patowner@test.com",
        username="patowner",
        password_hash=hash_password("PatOwner123!"),
        display_name="PAT Owner",
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create a valid PAT using the same pattern as factories.make_pat
    import hashlib
    import secrets

    prefix = secrets.token_hex(3)
    raw_secret = secrets.token_urlsafe(32)
    raw_token = f"fdp_pat_{prefix}_{raw_secret}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    pat = ApiToken(
        user_id=user.id,
        name="test-token",
        token_prefix=prefix,
        token_hash=token_hash,
        role=ApiTokenRole.editor,
        all_collections=True,
        allow_deletion=False,
        admin_scope=False,
    )
    db.add(pat)
    db.commit()
    db.refresh(pat)

    try:
        req = _mock_request()
        resolved_user, resolved_pat = _resolve_identity(req, token=raw_token, db=db)

        assert resolved_user.id == user.id
        assert resolved_pat is not None
        assert resolved_pat.id == pat.id
        assert req.state.pat is resolved_pat
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# PAT routing — invalid hash (valid prefix, wrong token)
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_pat_prefix_valid_hash_invalid_token_returns_401(db: Session):
    """A token with the fdp_pat_ prefix but an invalid/wrong secret returns 401."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    user = User(
        email="badpat@test.com",
        username="badpat",
        password_hash=hash_password("BadPat123!"),
        display_name="Bad PAT User",
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        req = _mock_request()
        with pytest.raises(__import__("fastapi").HTTPException) as exc_info:
            _resolve_identity(req, token="fdp_pat_abc123_wrong_secret_here", db=db)

        assert exc_info.value.status_code == 401
        assert "Invalid or revoked access token" in exc_info.value.detail
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# PAT — inactive user
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_pat_valid_token_user_disabled_returns_401(db: Session):
    """A PAT for a disabled user returns 401 because _resolve_pat rejects inactive users."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    user = User(
        email="inactive@test.com",
        username="inactiveuser",
        password_hash=hash_password("Inactive123!"),
        display_name="Inactive User",
        role=UserRole.user,
        is_active=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    import hashlib
    import secrets

    prefix = secrets.token_hex(3)
    raw_secret = secrets.token_urlsafe(32)
    raw_token = f"fdp_pat_{prefix}_{raw_secret}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    pat = ApiToken(
        user_id=user.id,
        name="test-token",
        token_prefix=prefix,
        token_hash=token_hash,
        role=ApiTokenRole.viewer,
        all_collections=True,
    )
    db.add(pat)
    db.commit()
    db.refresh(pat)

    try:
        req = _mock_request()
        with pytest.raises(__import__("fastapi").HTTPException) as exc_info:
            _resolve_identity(req, token=raw_token, db=db)

        # _resolve_pat returns None for inactive users, so the token is rejected
        # with the same 401 as a bad-hash token (PAT prefix detected, resolution failed)
        assert exc_info.value.status_code == 401
        assert "Invalid or revoked access token" in exc_info.value.detail
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# JWT — valid
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_jwt_valid_token_returns_user(db: Session):
    """A valid JWT Bearer token returns the corresponding user."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    user = User(
        email="jwtuser@test.com",
        username="jwtuser",
        password_hash=hash_password("JwtUser123!"),
        display_name="JWT User",
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _jwt_token(user.id)

    try:
        req = _mock_request()
        resolved_user, resolved_pat = _resolve_identity(req, token=token, db=db)

        assert resolved_user.id == user.id
        assert resolved_pat is None
        assert req.state.pat is None  # JWT path sets pat = None
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# JWT — expired
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_jwt_expired_token_returns_401(db: Session):
    """An expired JWT returns 401."""
    settings = get_settings()
    original = settings.auth.mode
    original_secret = settings.auth.secret_key
    settings.auth.mode = "multi"

    user = User(
        email="expired@test.com",
        username="expireduser",
        password_hash=hash_password("Expired123!"),
        display_name="Expired User",
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create a token that expired 1 hour ago
    expired_payload = {
        "sub": str(user.id),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    expired_token = jwt.encode(expired_payload, original_secret, algorithm="HS256")

    try:
        req = _mock_request()
        with pytest.raises(__import__("fastapi").HTTPException) as exc_info:
            _resolve_identity(req, token=expired_token, db=db)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# JWT — malformed / invalid
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_jwt_malformed_token_returns_401(db: Session):
    """A malformed JWT (bad signature / garbage) returns 401."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    try:
        req = _mock_request()
        with pytest.raises(__import__("fastapi").HTTPException) as exc_info:
            _resolve_identity(req, token="not.a.valid.jwt.token", db=db)

        assert exc_info.value.status_code == 401
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# JWT — nonexistent user
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_jwt_valid_but_user_deleted_returns_401(db: Session):
    """A structurally valid JWT whose user was deleted returns 401."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    user = User(
        email="deleteduser@test.com",
        username="deleteduser",
        password_hash=hash_password("Deleted123!"),
        display_name="Deleted User",
        role=UserRole.user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _jwt_token(user.id)

    # Delete the user
    db.delete(user)
    db.commit()

    try:
        req = _mock_request()
        with pytest.raises(__import__("fastapi").HTTPException) as exc_info:
            _resolve_identity(req, token=token, db=db)

        assert exc_info.value.status_code == 401
        assert "User not found" in exc_info.value.detail
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# JWT — password change invalidation
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_jwt_token_issued_before_password_change_returns_401(db: Session):
    """A JWT issued before a password change is rejected with 401."""
    settings = get_settings()
    original = settings.auth.mode
    original_secret = settings.auth.secret_key
    settings.auth.mode = "multi"

    user = User(
        email="pwdchg@test.com",
        username="pwdchguser",
        password_hash=hash_password("PwdChg123!"),
        display_name="Password Changed User",
        role=UserRole.user,
        # Simulate a password change that happened 1 hour ago
        password_changed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create a JWT that was issued 2 hours ago (before password_changed_at)
    old_payload = {
        "sub": str(user.id),
        "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    old_token = jwt.encode(old_payload, original_secret, algorithm="HS256")

    try:
        req = _mock_request()
        with pytest.raises(__import__("fastapi").HTTPException) as exc_info:
            _resolve_identity(req, token=old_token, db=db)

        assert exc_info.value.status_code == 401
        assert "Token invalidated by password change" in exc_info.value.detail
    finally:
        settings.auth.mode = original


@pytest.mark.security
def test_jwt_token_issued_after_password_change_is_valid(db: Session):
    """A JWT issued after the last password change is accepted."""
    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    user = User(
        email="newpwd@test.com",
        username="newpwduser",
        password_hash=hash_password("NewPwd123!"),
        display_name="New Password User",
        role=UserRole.user,
        # Password changed 1 hour ago
        password_changed_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Token issued now (after password change)
    token = _jwt_token(user.id)

    try:
        req = _mock_request()
        resolved_user, resolved_pat = _resolve_identity(req, token=token, db=db)

        assert resolved_user.id == user.id
        assert resolved_pat is None
    finally:
        settings.auth.mode = original


# ---------------------------------------------------------------------------
# require_admin — PAT without admin_scope on admin user
# ---------------------------------------------------------------------------

@pytest.mark.security
def test_require_admin_rejects_non_admin_scope_pat(db: Session):
    """require_admin returns 403 when a PAT lacks admin_scope even if user is admin."""
    from fastapi import HTTPException

    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    admin_user = User(
        email="adminpat@test.com",
        username="adminpat",
        password_hash=hash_password("AdminPat123!"),
        display_name="Admin PAT User",
        role=UserRole.admin,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    import hashlib
    import secrets

    prefix = secrets.token_hex(3)
    raw_secret = secrets.token_urlsafe(32)
    raw_token = f"fdp_pat_{prefix}_{raw_secret}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    pat = ApiToken(
        user_id=admin_user.id,
        name="test-token",
        token_prefix=prefix,
        token_hash=token_hash,
        role=ApiTokenRole.viewer,
        all_collections=True,
        admin_scope=False,
    )
    db.add(pat)
    db.commit()
    db.refresh(pat)

    try:
        req = _mock_request()
        req.state.pat = pat

        with pytest.raises(HTTPException) as exc_info:
            require_admin(current_user=admin_user, pat=pat)

        assert exc_info.value.status_code == 403
        assert "admin_scope" in exc_info.value.detail
    finally:
        settings.auth.mode = original


@pytest.mark.security
def test_require_admin_accepts_admin_scope_pat(db: Session):
    """require_admin allows a PAT with admin_scope=True on an admin user."""
    from fastapi import HTTPException

    settings = get_settings()
    original = settings.auth.mode
    settings.auth.mode = "multi"

    admin_user = User(
        email="adminscope@test.com",
        username="adminscope",
        password_hash=hash_password("AdminScope123!"),
        display_name="Admin Scope User",
        role=UserRole.admin,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    import hashlib
    import secrets

    prefix = secrets.token_hex(3)
    raw_secret = secrets.token_urlsafe(32)
    raw_token = f"fdp_pat_{prefix}_{raw_secret}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    pat = ApiToken(
        user_id=admin_user.id,
        name="test-token",
        token_prefix=prefix,
        token_hash=token_hash,
        role=ApiTokenRole.editor,
        all_collections=True,
        admin_scope=True,
    )
    db.add(pat)
    db.commit()
    db.refresh(pat)

    try:
        req = _mock_request()
        req.state.pat = pat

        result = require_admin(current_user=admin_user, pat=pat)
        assert result.id == admin_user.id
    except HTTPException:
        pytest.fail("require_admin raised HTTPException for admin_scope=True PAT")
    finally:
        settings.auth.mode = original
