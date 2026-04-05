"""Database session management."""

from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from fourdpocket.config import get_settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        db_url = settings.database.url

        if db_url.startswith("sqlite"):
            db_path = db_url.replace("sqlite:///", "")
            if db_path.startswith("./"):
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            connect_args = {"check_same_thread": False}
        else:
            connect_args = {}

        _engine = create_engine(
            db_url,
            echo=settings.database.echo,
            connect_args=connect_args,
        )

        # Enable SQLite foreign key enforcement
        if db_url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    return _engine


def get_session():
    engine = get_engine()
    with Session(engine) as session:
        yield session


def _ensure_columns(engine):
    """Add missing columns to existing tables (safe for SQLite, idempotent)."""
    from sqlmodel import text, Session

    migrations = [
        ("knowledge_items", "favicon_url", "TEXT"),
        ("knowledge_items", "reading_status", "VARCHAR DEFAULT 'unread'"),
        ("knowledge_items", "read_at", "TIMESTAMP"),
        ("notes", "is_favorite", "BOOLEAN DEFAULT 0"),
        ("notes", "is_archived", "BOOLEAN DEFAULT 0"),
        ("notes", "reading_status", "VARCHAR DEFAULT 'unread'"),
        ("notes", "reading_progress", "INTEGER DEFAULT 0"),
        ("highlights", "note_id", "TEXT REFERENCES notes(id)"),
        ("rss_feeds", "format", "VARCHAR DEFAULT 'rss'"),
        ("rss_feeds", "mode", "VARCHAR DEFAULT 'auto'"),
        ("rss_feeds", "filters", "TEXT"),
        ("rss_feeds", "last_error", "TEXT"),
        ("rss_feeds", "error_count", "INTEGER DEFAULT 0"),
        ("shares", "public", "BOOLEAN DEFAULT 0"),
        ("users", "password_changed_at", "TIMESTAMP"),
    ]

    with Session(engine) as db:
        for table, column, col_type in migrations:
            try:
                db.exec(text(f"SELECT {column} FROM {table} LIMIT 0"))
            except Exception:
                try:
                    db.exec(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                    db.commit()
                except Exception:
                    db.rollback()


def init_db():
    import fourdpocket.models  # noqa: F401 - ensure all models are registered

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _ensure_columns(engine)


def reset_engine():
    """Reset engine for testing."""
    global _engine
    _engine = None
