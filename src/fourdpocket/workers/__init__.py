"""Background workers using Huey with SQLite backend."""

from pathlib import Path

from huey import SqliteHuey

from fourdpocket.config import get_settings

settings = get_settings()
# Resolve to absolute path so Huey can open the DB regardless of CWD
base = settings.storage.base_path
base_path = Path(base).expanduser().resolve()
base_path.mkdir(parents=True, exist_ok=True)

huey = SqliteHuey(
    name="4dpocket",
    filename=str(base_path / "huey_tasks.db"),
    immediate=False,
)
