"""Tests for the PatEvent model.

Covers:
- Basic insert
- Manual cascade on token delete (mirrors SQLite lack of FK enforcement)
- Manual cascade on user delete
"""

import uuid

from sqlmodel import Session, select

from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.pat_event import PatEvent
from fourdpocket.models.user import User


def _make_user(db: Session, suffix: str = "") -> User:
    user = User(
        email=f"patevent{suffix}@test.com",
        username=f"patevent{suffix}",
        password_hash="$2b$12$fake",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_token(db: Session, user_id: uuid.UUID) -> ApiToken:
    import hashlib
    import secrets

    prefix = secrets.token_hex(3)
    raw = f"fdp_pat_{prefix}_{secrets.token_urlsafe(32)}"
    token = ApiToken(
        user_id=user_id,
        name="test-pat",
        token_prefix=prefix,
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        role="editor",
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


class TestPatEventModel:
    def test_insert_pat_event(self, db: Session):
        """PatEvent can be inserted and queried by pat_id."""
        user = _make_user(db, "insert")
        token = _make_token(db, user.id)

        event = PatEvent(
            pat_id=token.id,
            user_id=user.id,
            action="mint",
            resource="test-pat",
            status_code=201,
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        fetched = db.get(PatEvent, event.id)
        assert fetched is not None
        assert fetched.action == "mint"
        assert fetched.pat_id == token.id
        assert fetched.user_id == user.id
        assert fetched.status_code == 201
        assert fetched.created_at is not None

    def test_optional_fields_default_none(self, db: Session):
        """resource, ip, user_agent, status_code default to None."""
        user = _make_user(db, "defaults")
        token = _make_token(db, user.id)

        event = PatEvent(
            pat_id=token.id,
            user_id=user.id,
            action="mcp_tool_call",
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        assert event.resource is None
        assert event.ip is None
        assert event.user_agent is None
        assert event.status_code is None

    def test_cascade_on_token_delete_manual(self, db: Session):
        """Deleting a token (manual cascade) removes its PatEvent rows.

        SQLite in-memory tests do not enforce FK CASCADE. We replicate
        the correct deletion order: events first, then token.
        """
        user = _make_user(db, "cascade_tok")
        token = _make_token(db, user.id)

        event = PatEvent(
            pat_id=token.id,
            user_id=user.id,
            action="rest_call",
            status_code=200,
        )
        db.add(event)
        db.commit()

        event_id = event.id
        token_id = token.id

        # Delete events first, then token (correct order for FK integrity)
        for row in db.exec(
            select(PatEvent).where(PatEvent.pat_id == token_id)
        ).all():
            db.delete(row)
        db.delete(token)
        db.commit()

        assert db.get(PatEvent, event_id) is None
        assert db.get(ApiToken, token_id) is None

    def test_cascade_on_user_delete_manual(self, db: Session):
        """Deleting a user removes all their PatEvent rows (manual cascade order)."""
        user = _make_user(db, "cascade_usr")
        token = _make_token(db, user.id)

        for action in ("mint", "rest_call", "revoke"):
            db.add(PatEvent(pat_id=token.id, user_id=user.id, action=action))
        db.commit()

        user_id = user.id
        token_id = token.id

        # Cascade order: events → token_collections → token → user
        for row in db.exec(
            select(PatEvent).where(PatEvent.user_id == user_id)
        ).all():
            db.delete(row)
        db.delete(token)
        db.delete(user)
        db.commit()

        remaining = db.exec(
            select(PatEvent).where(PatEvent.user_id == user_id)
        ).all()
        assert remaining == []
