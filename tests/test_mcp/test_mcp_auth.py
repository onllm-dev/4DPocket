"""PATTokenVerifier tests — validates tokens against the database via sync DB lookup."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from fourdpocket.api.api_token_utils import generate_token
from fourdpocket.mcp.auth import PATTokenVerifier
from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.base import ApiTokenRole
from fourdpocket.models.user import User


def _make_user(db: Session, email="auth@example.com") -> User:
    u = User(
        email=email,
        username=email.split("@")[0],
        password_hash="x",
        display_name="T",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _mint(db: Session, user_id: uuid.UUID, **overrides) -> tuple[str, ApiToken]:
    gen = generate_token()
    pat = ApiToken(
        user_id=user_id,
        name="verifier-test",
        token_prefix=gen.prefix,
        token_hash=gen.token_hash,
        role=ApiTokenRole.viewer,
        all_collections=True,
        include_uncollected=True,
    )
    for k, v in overrides.items():
        setattr(pat, k, v)
    db.add(pat)
    db.commit()
    db.refresh(pat)
    return gen.plaintext, pat


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_verify_valid_token(engine):
    # Use a session that shares the test engine
    import fourdpocket.db.session as db_module

    orig = db_module._engine
    db_module._engine = engine
    try:
        with Session(engine) as db:
            user = _make_user(db)
            plaintext, _pat = _mint(db, user.id)
            user_id_str = str(user.id)

        result = _run(PATTokenVerifier().verify_token(plaintext))
        assert result is not None
        assert result.token == plaintext
        assert result.client_id == user_id_str
        assert "mcp" in result.scopes
        assert "viewer" in result.scopes
    finally:
        db_module._engine = orig


def test_verify_invalid_token(engine):
    import fourdpocket.db.session as db_module

    orig = db_module._engine
    db_module._engine = engine
    try:
        result = _run(PATTokenVerifier().verify_token("fdp_pat_nope_nothere"))
        assert result is None
    finally:
        db_module._engine = orig


def test_verify_revoked_token(engine):
    import fourdpocket.db.session as db_module

    orig = db_module._engine
    db_module._engine = engine
    try:
        with Session(engine) as db:
            user = _make_user(db, email="revoke@example.com")
            plaintext, pat = _mint(db, user.id)
            pat.revoked_at = datetime.now(timezone.utc)
            db.add(pat)
            db.commit()
        result = _run(PATTokenVerifier().verify_token(plaintext))
        assert result is None
    finally:
        db_module._engine = orig


def test_verify_expired_token(engine):
    import fourdpocket.db.session as db_module

    orig = db_module._engine
    db_module._engine = engine
    try:
        with Session(engine) as db:
            user = _make_user(db, email="exp@example.com")
            plaintext, pat = _mint(
                db,
                user.id,
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
        result = _run(PATTokenVerifier().verify_token(plaintext))
        assert result is None
    finally:
        db_module._engine = orig


def test_verify_scopes_reflect_flags(engine):
    import fourdpocket.db.session as db_module

    orig = db_module._engine
    db_module._engine = engine
    try:
        with Session(engine) as db:
            user = _make_user(db, email="scopes@example.com")
            plaintext, _pat = _mint(
                db,
                user.id,
                role=ApiTokenRole.editor,
                allow_deletion=True,
                admin_scope=True,
            )
        result = _run(PATTokenVerifier().verify_token(plaintext))
        assert result is not None
        assert "editor" in result.scopes
        assert "knowledge:delete" in result.scopes
        assert "admin" in result.scopes
    finally:
        db_module._engine = orig
