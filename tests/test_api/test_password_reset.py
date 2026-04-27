"""Tests for the password-reset flow.

Regression tests for:
- POST /api/v1/auth/password-reset/request  (no-leak, token creation)
- POST /api/v1/auth/password-reset/confirm  (happy path, expired, already used, weak password)
"""

from datetime import datetime, timedelta, timezone

import pytest

from fourdpocket.auth.tokens import generate_token, hash_token
from fourdpocket.models.password_reset import PasswordResetToken


def _register(client, email="reset@example.com", username="resetuser", password="Reset123!"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )


def _request_reset(client, identifier):
    return client.post(
        "/api/v1/auth/password-reset/request",
        json={"email_or_username": identifier},
    )


def _confirm_reset(client, token, new_password):
    return client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": new_password},
    )


# ── no-leak behaviour ─────────────────────────────────────────────────────────

def test_request_reset_nonexistent_user_returns_200(client):
    """Request for unknown email must return 200 + {sent: true} (no enumeration)."""
    response = _request_reset(client, "ghost@example.com")
    assert response.status_code == 200
    assert response.json() == {"sent": True}


def test_request_reset_known_user_returns_200(client):
    _register(client)
    response = _request_reset(client, "reset@example.com")
    assert response.status_code == 200
    assert response.json() == {"sent": True}


def test_request_reset_by_username(client):
    _register(client)
    response = _request_reset(client, "resetuser")
    assert response.status_code == 200
    assert response.json() == {"sent": True}


# ── happy path ────────────────────────────────────────────────────────────────

def test_confirm_reset_updates_password(client, db):
    """Valid token + strong new password → 204, then login with new password works."""
    _register(client)

    # Inject a fresh token directly into the DB (bypasses email)
    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "reset@example.com")).first()
    raw, token_hash = generate_token()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(token)
    db.commit()

    response = _confirm_reset(client, raw, "NewPass456!")
    assert response.status_code == 204

    # Old password must fail
    login_old = client.post(
        "/api/v1/auth/login",
        data={"username": "reset@example.com", "password": "Reset123!"},
    )
    assert login_old.status_code == 401

    # New password must succeed
    login_new = client.post(
        "/api/v1/auth/login",
        data={"username": "reset@example.com", "password": "NewPass456!"},
    )
    assert login_new.status_code == 200
    assert "access_token" in login_new.json()


def test_confirm_reset_token_is_single_use(client, db):
    """Second use of the same token must return 400."""
    _register(client)

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "reset@example.com")).first()
    raw, token_hash = generate_token()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(token)
    db.commit()

    _confirm_reset(client, raw, "NewPass456!")

    second = _confirm_reset(client, raw, "AnotherPass789!")
    assert second.status_code == 400
    assert "already been used" in second.json()["detail"]


def test_confirm_reset_expired_token(client, db):
    """Expired token must return 400."""
    _register(client)

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "reset@example.com")).first()
    raw, token_hash = generate_token()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),  # already expired
    )
    db.add(token)
    db.commit()

    response = _confirm_reset(client, raw, "NewPass456!")
    assert response.status_code == 400
    assert "expired" in response.json()["detail"]


def test_confirm_reset_invalid_token(client):
    """Unknown token must return 400."""
    response = _confirm_reset(client, "notavalidtoken", "NewPass456!")
    assert response.status_code == 400


@pytest.mark.parametrize("password", [
    "short1!",         # too short
    "nouppercase1!",   # no uppercase
    "NoDigitSpecial!", # no digit
    "NoSpecial1",      # no special char
])
def test_confirm_reset_weak_password(client, db, password):
    """Weak new_password must be rejected with 422."""
    _register(client)

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "reset@example.com")).first()
    raw, token_hash = generate_token()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(token)
    db.commit()

    response = _confirm_reset(client, raw, password)
    assert response.status_code == 422


def test_confirm_reset_invalidates_old_jwt(client, db):
    """After password reset, JWTs issued before the reset are rejected."""
    _register(client)
    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "reset@example.com", "password": "Reset123!"},
    )
    old_token = login_resp.json()["access_token"]
    old_headers = {"Authorization": f"Bearer {old_token}"}

    # Verify the old token works before reset
    assert client.get("/api/v1/auth/me", headers=old_headers).status_code == 200

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "reset@example.com")).first()
    raw, token_hash = generate_token()
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    db.add(token)
    db.commit()

    _confirm_reset(client, raw, "NewPass456!")

    # Old JWT must be rejected because iat < password_changed_at
    me_resp = client.get("/api/v1/auth/me", headers=old_headers)
    assert me_resp.status_code == 401
