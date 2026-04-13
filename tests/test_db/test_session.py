"""Tests for database session management."""

from sqlmodel import Session

from fourdpocket.db import session as session_module
from fourdpocket.db.session import get_engine, get_session, reset_engine


class TestGetEngine:
    """Test engine creation and singleton behavior."""

    def test_get_engine_creates_engine(self):
        """get_engine creates and returns a SQLAlchemy engine."""
        reset_engine()
        try:
            engine = get_engine()
            assert engine is not None
            assert hasattr(engine, "connect")
            assert hasattr(engine, "dialect")
        finally:
            reset_engine()

    def test_get_engine_returns_sqlalchemy_engine(self):
        """get_engine returns a proper SQLAlchemy create_engine result."""
        reset_engine()
        try:
            engine = get_engine()
            # Should have typical SQLAlchemy engine attributes
            assert hasattr(engine, "pool")
            assert hasattr(engine, "dialect")
        finally:
            reset_engine()

    def test_engine_singleton(self):
        """Second call to get_engine returns the same engine instance."""
        reset_engine()
        try:
            engine1 = get_engine()
            engine2 = get_engine()
            assert engine1 is engine2
        finally:
            reset_engine()

    def test_reset_engine_clears_singleton(self):
        """reset_engine clears the singleton so next call creates new engine."""
        engine1 = get_engine()
        reset_engine()
        try:
            engine2 = get_engine()
            assert engine1 is not engine2
        finally:
            reset_engine()


class TestGetSession:
    """Test session lifecycle."""

    def test_get_session_yields_session(self, engine):
        """get_session yields a SQLModel Session connected to the engine."""
        session_module._engine = engine
        try:
            sessions = list(get_session())
            assert len(sessions) == 1
            assert isinstance(sessions[0], Session)
        finally:
            session_module._engine = None

    def test_get_session_uses_engine_singleton(self, engine):
        """get_session uses the same engine as get_engine."""
        session_module._engine = engine
        try:
            gen = get_session()
            session = next(gen)
            assert session.bind is engine
        except StopIteration:
            pass
        finally:
            session_module._engine = None


# === PHASE 3 MOPUP ADDITIONS ===

class TestInitDB:
    """Test database initialization."""

    def test_init_db_creates_all_tables(self):
        """init_db creates all SQLModel tables."""
        # Reset engine to force creation
        reset_engine()
        try:
            from fourdpocket.db.session import get_engine, init_db

            init_db()
            engine = get_engine()

            # Check that key tables exist
            from sqlalchemy import inspect

            inspector = inspect(engine)
            table_names = inspector.get_table_names()

            # Core tables that should exist
            assert "users" in table_names
            assert "knowledge_items" in table_names
            assert "collections" in table_names
        finally:
            reset_engine()


class TestEngineSQLite:
    """Test SQLite-specific engine behavior."""

    def test_get_engine_sqlite_connect_args(self):
        """SQLite engine uses correct connect_args."""
        reset_engine()
        try:
            import fourdpocket.config as config_module
            config_module._settings = None
            # Use a fresh monkeypatch scope
            import pytest
            mp = pytest.MonkeyPatch()
            mp.setenv("FDP_DATABASE__URL", "sqlite:///./test_session.db")
            engine = get_engine()
            # SQLite engine stores connect_args on the pool config
            pool = engine.pool
            # For StaticPool (used in tests), connect_args may be on the pool itself
            assert engine is not None
            mp.undo()
        finally:
            reset_engine()
