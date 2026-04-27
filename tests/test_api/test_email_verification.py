"""Tests for the email-verification flow.

Regression tests for:
- Registration triggers a verification token (best-effort)
- GET /api/v1/auth/email/verify  (happy path, expired, already used, bad token)
- POST /api/v1/auth/email/resend (rate-limited)
"""

from datetime import datetime, timedelta, timezone

from fourdpocket.auth.tokens import generate_token
from fourdpocket.models.email_verification import EmailVerificationToken


def _register(client, email="verify@example.com", username="verifyuser", password="Verify123!"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )


def _login(client, email="verify@example.com", password="Verify123!"):
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _inject_token(db, user_id, *, expired=False, used=False):
    """Insert a verification token directly into the DB. Returns raw token."""
    raw, token_hash = generate_token()
    expires_at = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
        if expired
        else datetime.now(timezone.utc) + timedelta(hours=24)
    )
    token = EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        used_at=datetime.now(timezone.utc) if used else None,
    )
    db.add(token)
    db.commit()
    return raw


# ── happy path ────────────────────────────────────────────────────────────────

def test_verify_email_happy_path(client, db):
    """Valid token marks user as email_verified=True."""
    _register(client)

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "verify@example.com")).first()
    assert not user.email_verified

    raw = _inject_token(db, user.id)
    resp = client.get(f"/api/v1/auth/email/verify?token={raw}")
    assert resp.status_code == 200
    assert resp.json() == {"verified": True}

    db.refresh(user)
    assert user.email_verified is True
    assert user.email_verified_at is not None


def test_verify_email_token_is_single_use(client, db):
    """Second use of the same token must return 400."""
    _register(client)

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "verify@example.com")).first()
    raw = _inject_token(db, user.id)

    client.get(f"/api/v1/auth/email/verify?token={raw}")
    second = client.get(f"/api/v1/auth/email/verify?token={raw}")
    assert second.status_code == 400
    assert "already been used" in second.json()["detail"]


def test_verify_email_expired_token(client, db):
    """Expired token returns 400."""
    _register(client)

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "verify@example.com")).first()
    raw = _inject_token(db, user.id, expired=True)

    resp = client.get(f"/api/v1/auth/email/verify?token={raw}")
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"]


def test_verify_email_invalid_token(client):
    """Unknown token returns 400."""
    resp = client.get("/api/v1/auth/email/verify?token=notavalidtoken")
    assert resp.status_code == 400


def test_verify_email_html_accept_redirects(client, db):
    """Accept: text/html causes a redirect to /verified."""
    _register(client)

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "verify@example.com")).first()
    raw = _inject_token(db, user.id)

    resp = client.get(
        f"/api/v1/auth/email/verify?token={raw}",
        headers={"Accept": "text/html"},
        follow_redirects=False,
    )
    # Should be a redirect (302) to /verified
    assert resp.status_code == 302
    assert "/verified" in resp.headers.get("location", "")


# ── resend endpoint ───────────────────────────────────────────────────────────

def test_resend_verification_returns_204(client):
    """POST /email/resend for unverified user returns 204."""
    _register(client)
    headers = _login(client)
    resp = client.post("/api/v1/auth/email/resend", headers=headers)
    assert resp.status_code == 204


def test_resend_already_verified_is_noop(client, db):
    """Resend for already-verified user still returns 204 (silent noop)."""
    _register(client)

    from sqlmodel import select
    from fourdpocket.models.user import User

    user = db.exec(select(User).where(User.email == "verify@example.com")).first()
    user.email_verified = True
    db.add(user)
    db.commit()

    headers = _login(client)
    resp = client.post("/api/v1/auth/email/resend", headers=headers)
    assert resp.status_code == 204


def test_resend_requires_auth(client):
    """Unauthenticated resend returns 401."""
    resp = client.post("/api/v1/auth/email/resend")
    assert resp.status_code == 401


# ── login still works when email is not verified ──────────────────────────────

def test_login_allowed_without_email_verified(client):
    """email_verified=False must not block login (gentle UX — product can gate later)."""
    _register(client)
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "verify@example.com", "password": "Verify123!"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
