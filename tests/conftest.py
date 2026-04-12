"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import fourdpocket.models  # noqa: F401 — register all models before create_all
from fourdpocket.config import get_settings


@pytest.fixture(name="engine", scope="function")
def test_engine():
    # StaticPool ensures all connections share the same in-memory database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # Initialize FTS5 table for search tests
    from fourdpocket.search.sqlite_fts import init_chunks_fts, init_fts

    with Session(engine) as session:
        init_fts(session)
        init_chunks_fts(session)

    yield engine
    engine.dispose()


@pytest.fixture(name="db")
def test_db(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def test_client(engine):
    import fourdpocket.db.session as db_module

    # Monkey-patch the engine so get_session() uses our test engine
    original_engine = db_module._engine
    db_module._engine = engine

    from fourdpocket.main import app

    # Force multi-user mode (requires explicit auth)
    settings = get_settings()
    original_mode = settings.auth.mode
    settings.auth.mode = "multi"

    # Disable rate limiting for tests by removing middleware state
    # We rebuild the middleware stack by removing RateLimitMiddleware
    app.user_middleware = [
        m for m in app.user_middleware
        if not (hasattr(m, "cls") and m.cls.__name__ == "RateLimitMiddleware")
    ]
    app.middleware_stack = app.build_middleware_stack()

    # Clear in-endpoint rate limiters between tests
    import fourdpocket.api.auth as auth_module
    if hasattr(auth_module, "_failed_login_attempts"):
        auth_module._failed_login_attempts.clear()
    if hasattr(auth_module, "_register_attempts"):
        auth_module._register_attempts.clear()
    import fourdpocket.api.sharing as sharing_module
    if hasattr(sharing_module, "_public_token_attempts"):
        sharing_module._public_token_attempts.clear()

    with TestClient(app) as c:
        yield c

    settings.auth.mode = original_mode
    db_module._engine = original_engine


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(client):
    """Register a user and return auth headers."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "TestPass123!",
            "display_name": "Test User",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "TestPass123!"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(name="second_user_headers")
def second_user_headers_fixture(client):
    """Register a second user and return auth headers."""
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "user2@example.com",
            "username": "seconduser",
            "password": "TestPass456!",
            "display_name": "Second User",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "user2@example.com", "password": "TestPass456!"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
