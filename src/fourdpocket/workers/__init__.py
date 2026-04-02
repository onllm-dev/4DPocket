"""Background workers using Huey with SQLite backend."""

from pathlib import Path

from huey import SqliteHuey

from fourdpocket.config import get_settings

settings = get_settings()
data_dir = Path(settings.storage.base_path)
data_dir.mkdir(parents=True, exist_ok=True)

huey = SqliteHuey(
    name="4dpocket",
    filename=str(data_dir / "huey_tasks.db"),
    immediate=False,
)
