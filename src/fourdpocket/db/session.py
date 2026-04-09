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
    """Auto-sync: add any columns defined in models but missing from the database.

    Compares SQLModel metadata against the live database schema using
    SQLAlchemy inspection. This eliminates the need for a manual migration
    list — every new model column is picked up automatically on startup.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())

    # Map SQLAlchemy types to portable SQL type strings
    def _sql_type(col):
        try:
            return col.type.compile(engine.dialect)
        except Exception:
            return "TEXT"

    with engine.connect() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if table.name not in db_tables:
                continue  # table doesn't exist yet; create_all handles it

            db_columns = {c["name"] for c in inspector.get_columns(table.name)}

            for col in table.columns:
                if col.name in db_columns:
                    continue
                col_type = _sql_type(col)
                try:
                    conn.execute(text(
                        f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}'
                    ))
                    conn.commit()
                except Exception:
                    conn.rollback()


def init_db():
    import fourdpocket.models  # noqa: F401 - ensure all models are registered

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _ensure_columns(engine)


def reset_engine():
    """Reset engine for testing."""
    global _engine
    _engine = None
