"""Local filesystem storage with user-scoped paths."""

import uuid
from pathlib import Path

from fourdpocket.config import get_settings


class LocalStorage:
    """File storage with user-scoped directory structure."""

    def __init__(self, base_path: str | None = None):
        if base_path is None:
            base_path = get_settings().storage.base_path
        self._base = Path(base_path)

    def _safe_path(self, relative_path: str) -> Path:
        """Resolve path and ensure it stays within the storage directory."""
        resolved = (self._base / relative_path).resolve()
        if not str(resolved).startswith(str(self._base.resolve())):
            raise ValueError("Path traversal detected")
        return resolved

    def _user_path(self, user_id: uuid.UUID, category: str) -> Path:
        path = self._base / str(user_id) / category
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_file(
        self,
        user_id: uuid.UUID,
        category: str,
        filename: str,
        data: bytes,
    ) -> str:
        """Save a file and return its relative path."""
        file_path = self._user_path(user_id, category) / filename
        file_path.write_bytes(data)
        return str(file_path.relative_to(self._base))

    def get_file(self, relative_path: str) -> bytes:
        """Read a file by its relative path."""
        file_path = self._safe_path(relative_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        return file_path.read_bytes()

    def delete_file(self, relative_path: str) -> None:
        """Delete a file by its relative path."""
        file_path = self._safe_path(relative_path)
        if file_path.exists():
            file_path.unlink()

    def get_absolute_path(self, relative_path: str) -> Path:
        """Get the absolute path for a relative storage path."""
        return self._safe_path(relative_path)

    def file_exists(self, relative_path: str) -> bool:
        """Check if a file exists."""
        return self._safe_path(relative_path).exists()
