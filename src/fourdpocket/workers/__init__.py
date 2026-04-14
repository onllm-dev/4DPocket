"""Background workers using Huey with SQLite backend."""

from huey import SqliteHuey

_huey_instance = None


def _get_huey():
    global _huey_instance
    if _huey_instance is None:
        from pathlib import Path

        from fourdpocket.config import get_settings

        settings = get_settings()
        base = settings.storage.base_path
        base_path = Path(base).expanduser().resolve()
        base_path.mkdir(parents=True, exist_ok=True)

        _huey_instance = SqliteHuey(
            name="4dpocket",
            filename=str(base_path / "huey_tasks.db"),
            immediate=False,
        )
    return _huey_instance


def __getattr__(name: str):
    if name == "huey":
        return _get_huey()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
