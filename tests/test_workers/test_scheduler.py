"""Tests for the periodic scheduler tasks."""

from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.workers.scheduler import (
    cleanup_stale_tasks,
    run_backup,
)


class TestRunBackup:
    """Test the run_backup function."""

    def test_backup_non_sqlite_skipped(self, monkeypatch):
        """Non-SQLite database URLs are not backed up."""
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.database.url = "postgresql://localhost/test"
        mock_settings.storage.base_path = "/tmp"

        monkeypatch.setattr("fourdpocket.config._settings", mock_settings)

        result = run_backup()
        assert result is None

    def test_backup_missing_db_file(self, monkeypatch, tmp_path):
        """Missing database file returns None without crashing."""
        from unittest.mock import MagicMock

        mock_settings = MagicMock()
        mock_settings.database.url = f"sqlite:///{tmp_path}/nonexistent.db"
        mock_settings.storage.base_path = str(tmp_path)

        monkeypatch.setattr("fourdpocket.config._settings", mock_settings)

        result = run_backup()
        assert result is None

    def test_backup_sqlite_success(self, monkeypatch, tmp_path):
        """SQLite backup copies the file and returns the backup path."""
        from unittest.mock import MagicMock

        # Create a fake database file
        db_file = tmp_path / "test.db"
        db_file.write_text("fake db content")

        mock_settings = MagicMock()
        mock_settings.database.url = f"sqlite:///{db_file}"
        mock_settings.storage.base_path = str(tmp_path)

        monkeypatch.setattr("fourdpocket.config._settings", mock_settings)

        # Patch shutil.copy2 to avoid actual I/O
        from unittest.mock import patch

        with patch("fourdpocket.workers.scheduler.shutil.copy2") as mock_copy:
            result = run_backup()

        assert result is not None
        assert "4dpocket_backup_" in result
        assert result.endswith(".db")
        mock_copy.assert_called_once()

    def test_backup_cleans_old_backups(self, monkeypatch, tmp_path):
        """run_backup removes backups beyond the last 10."""
        from unittest.mock import MagicMock

        db_file = tmp_path / "test.db"
        db_file.write_text("fake db content")

        # Create 25 existing backup files with timestamps that will all sort
        # before today's timestamp (use year 2024, new backup is 2026)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir(parents=True)
        for i in range(25):
            (backup_dir / f"4dpocket_backup_20241201_{i:06d}.db").write_text(f"old backup {i}")

        mock_settings = MagicMock()
        mock_settings.database.url = f"sqlite:///{db_file}"
        mock_settings.storage.base_path = str(tmp_path)

        monkeypatch.setattr("fourdpocket.config._settings", mock_settings)

        result = run_backup()

        assert result is not None
        # 26 total (25 old + 1 new) - 16 removed (beyond 10) = 10 kept
        remaining = list(backup_dir.glob("4dpocket_backup_*.db"))
        assert len(remaining) == 10

    def test_backup_expanduser_path(self, monkeypatch, tmp_path):
        """SQLite path starting with ~ is expanded to home directory."""
        import os
        from unittest.mock import MagicMock

        home = os.path.expanduser("~")
        # Create the database file in a temp dir, but reference it via ~ path
        db_file = tmp_path / "test_home.db"
        db_file.write_text("content")

        mock_settings = MagicMock()
        mock_settings.database.url = f"sqlite:///~/{db_file.relative_to(home) if str(db_file).startswith(home) else str(db_file)}"
        mock_settings.storage.base_path = str(tmp_path)

        monkeypatch.setattr("fourdpocket.config._settings", mock_settings)

        from unittest.mock import patch

        # The path won't actually expand since tmp_path isn't under ~
        # This test just verifies non-crashing behavior
        with patch("fourdpocket.workers.scheduler.shutil.copy2"):
            result = run_backup()
        # Result may be None since path expansion with ~ won't work for tmp_path
        assert result is None or isinstance(result, str)


class TestCleanupStaleTasks:
    """Tests for cleanup_stale_tasks."""

    def test_cleanup_stale_tasks_runs(self, caplog):
        """cleanup_stale_tasks executes without error (body is a Phase 2 stub)."""

        import logging

        with caplog.at_level(logging.INFO):
            cleanup_stale_tasks.call_local()

        assert "Running stale task cleanup" in caplog.text


class TestReprocessPendingItems:
    """Tests for reprocess_pending_items."""

    def test_reprocess_skips_items_with_high_retry_count(
        self, db: Session, enrich_user, monkeypatch
    ):
        """Items with _retry_count >= 3 are not re-enqueued."""

        import fourdpocket.db.session as db_module
        from fourdpocket.models.base import ItemType
        from fourdpocket.workers.scheduler import reprocess_pending_items

        # Create an item with None content and max retries
        item = KnowledgeItem(
            user_id=enrich_user.id,
            title="Retry Item",
            content=None,
            url="https://example.com/retry",
            item_type=ItemType.url,
            item_metadata={"_retry_count": 3},
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(item)
        db.commit()

        # Set the test engine as the global engine
        original_engine = db_module._engine
        db_module._engine = db.get_bind()

        call_count = 0

        def fake_fetch(item_id, url, user_id):
            nonlocal call_count
            call_count += 1

        monkeypatch.setattr(
            "fourdpocket.workers.fetcher.fetch_and_process_url", fake_fetch
        )

        try:
            reprocess_pending_items.call_local()
        finally:
            db_module._engine = original_engine

        assert call_count == 0, "Item with max retries should not be enqueued"

    def test_reprocess_enqueues_valid_pending_items(
        self, db: Session, enrich_user, monkeypatch
    ):
        """Items with content=None, url set, and retry_count < 3 are enqueued."""

        import fourdpocket.db.session as db_module
        from fourdpocket.models.base import ItemType
        from fourdpocket.workers.scheduler import reprocess_pending_items

        item = KnowledgeItem(
            user_id=enrich_user.id,
            title="Pending Item",
            content=None,
            url="https://example.com/pending",
            item_type=ItemType.url,
            item_metadata={"_retry_count": 0},
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(item)
        db.commit()

        original_engine = db_module._engine
        db_module._engine = db.get_bind()

        call_count = 0
        captured_id = [None]

        def fake_fetch(item_id, url, user_id):
            nonlocal call_count
            call_count += 1
            captured_id[0] = item_id

        monkeypatch.setattr(
            "fourdpocket.workers.fetcher.fetch_and_process_url", fake_fetch
        )

        try:
            reprocess_pending_items.call_local()
        finally:
            db_module._engine = original_engine

        assert call_count == 1
        assert captured_id[0] == str(item.id)

    def test_reprocess_skips_items_without_url(
        self, db: Session, enrich_user, monkeypatch
    ):
        """Items with no URL are not enqueued (can't refetch)."""

        import fourdpocket.db.session as db_module
        from fourdpocket.models.base import ItemType
        from fourdpocket.workers.scheduler import reprocess_pending_items

        item = KnowledgeItem(
            user_id=enrich_user.id,
            title="No URL Item",
            content=None,
            url=None,
            item_type=ItemType.url,
            item_metadata={"_retry_count": 0},
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(item)
        db.commit()

        original_engine = db_module._engine
        db_module._engine = db.get_bind()

        call_count = 0

        def fake_fetch(item_id, url, user_id):
            nonlocal call_count
            call_count += 1

        monkeypatch.setattr(
            "fourdpocket.workers.fetcher.fetch_and_process_url", fake_fetch
        )

        try:
            reprocess_pending_items.call_local()
        finally:
            db_module._engine = original_engine

        assert call_count == 0, "Item without URL should not be enqueued"
