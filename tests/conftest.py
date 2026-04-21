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


@pytest.fixture(autouse=True)
def reset_search_singleton():
    """Reset the search service singleton between tests."""
    import fourdpocket.search as search_module
    original = getattr(search_module, "_search_service", None)
    yield
    search_module._search_service = original


@pytest.fixture(autouse=True)
def reset_processor_registry():
    """Snapshot/restore the processor registry around every test.

    ``fourdpocket.processors.registry`` keeps two module-level lists
    (_REGISTRY, _PATTERNS). When tests register throwaway processors inside
    an xdist worker, any leak — even temporary — can flip the output of
    ``match_processor`` for later tests in the same worker, producing flaky
    failures like ``test_url_pattern_matching`` intermittently seeing a wrong
    processor class. Snapshotting covers the whole class of issues regardless
    of which test is to blame.
    """
    # Import eagerly so the full processor set is registered before we snapshot.
    import fourdpocket.processors  # noqa: F401
    from fourdpocket.processors import registry

    reg_before = dict(registry._REGISTRY)
    pat_before = list(registry._PATTERNS)
    try:
        yield
    finally:
        registry._REGISTRY.clear()
        registry._REGISTRY.update(reg_before)
        registry._PATTERNS[:] = pat_before


@pytest.fixture(autouse=True)
def reset_settings_singleton():
    """Reset the settings singleton between tests.

    The test_client fixture modifies settings.auth.mode = "multi" and restores
    it afterward, but if a test fails before restore runs, state leaks. This
    fixture ensures _settings is always reset to None after each test.
    """
    import fourdpocket.config as config_module
    yield
    config_module._settings = None


@pytest.fixture(autouse=True)
def clear_search_cache():
    """Clear FTS search cache between tests."""
    from fourdpocket.search.sqlite_fts import _search_cache
    yield
    _search_cache._cache.clear()


@pytest.fixture(name="mock_chat_provider")
def mock_chat_provider_fixture(monkeypatch):
    """Inject a deterministic mock chat provider for AI tests."""
    class MockChatProvider:
        def generate(self, prompt, **kwargs):
            return "mock response"
        def generate_json(self, prompt, schema=None, **kwargs):
            return {}

    provider = MockChatProvider()
    monkeypatch.setattr(
        "fourdpocket.ai.factory.get_chat_provider", lambda: provider
    )
    return provider


@pytest.fixture(name="mock_embedding_provider")
def mock_embedding_provider_fixture(monkeypatch):
    """Inject a mock embedding provider that returns fixed-dim vectors."""
    class MockEmbeddingProvider:
        dimensions = 384

        def embed(self, texts):
            return [[0.1] * 384 for _ in texts]

    provider = MockEmbeddingProvider()
    monkeypatch.setattr(
        "fourdpocket.ai.factory.get_embedding_provider", lambda: provider
    )
    return provider


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



@pytest.fixture(name="enrich_user")
def enrich_user_fixture(db):
    """Create a user for enrichment tests."""
    from fourdpocket.models.user import User

    user = User(
        email="enrichtest@example.com",
        username="enrichuser",
        password_hash="$2b$12$fakehash",
        display_name="Enrich Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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
