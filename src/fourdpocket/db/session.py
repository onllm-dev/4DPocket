"""Database session management."""

from pathlib import Path

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
    return _engine


def get_session():
    engine = get_engine()
    with Session(engine) as session:
        yield session


def init_db():
    import fourdpocket.models  # noqa: F401 — ensure all models are registered

    engine = get_engine()
    SQLModel.metadata.create_all(engine)


def reset_engine():
    """Reset engine for testing."""
    global _engine
    _engine = None
