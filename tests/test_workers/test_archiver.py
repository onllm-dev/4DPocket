"""Tests for the page archiver background task."""

import uuid

import pytest
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.workers.archiver import _update_item_archive, archive_page


def _make_archiver_user(db: Session):
    from fourdpocket.models.user import User

    user = User(
        email="archuser@test.com",
        username="archuser",
        password_hash="$2b$12$fake",
        display_name="Archive User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_archiver_item(db: Session, user) -> KnowledgeItem:
    item = KnowledgeItem(
        user_id=user.id,
        url="https://example.com/article",
        title="Archive Test",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


class TestArchivePage:
    """Test the archive_page Huey task."""

    def test_archive_page_invalid_scheme(self, db: Session, engine, monkeypatch):
        """Non-http URL raises ValueError."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        with pytest.raises(ValueError, match="Invalid URL scheme"):
            archive_page.call_local(
                str(uuid.uuid4()), "ftp://example.com/file", str(uuid.uuid4())
            )

    def test_archive_page_ssrf_blocked(self, db: Session, engine, monkeypatch):
        """Internal network URL is blocked."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_archiver_user(db)
        item = _make_archiver_item(db, user)

        result = archive_page.call_local(
            str(item.id), "https://127.0.0.1/internal", str(user.id)
        )
        assert result["status"] == "blocked"

    def test_archive_page_no_tool_returns_skipped(self, db: Session, engine, monkeypatch):
        """Neither monolith nor playwright available returns skipped."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_archiver_user(db)
        item = _make_archiver_item(db, user)

        # Neither subprocess nor playwright available
        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.setattr("asyncio.run", lambda coro: None)
        monkeypatch.setattr(
            "playwright.async_api.async_playwright",
            lambda: (_ for _ in ()).throw(ImportError("playwright not installed")),
        )

        result = archive_page.call_local(str(item.id), "https://example.com/article", str(user.id))
        assert result["status"] == "skipped"

    def test_archive_page_monolith_success(self, db: Session, engine, monkeypatch):
        """monolith binary succeeds and returns success."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_archiver_user(db)
        item = _make_archiver_item(db, user)

        # Make monolith available
        monkeypatch.setattr(
            "shutil.which",
            lambda name: "/usr/bin/monolith" if name == "monolith" else None,
        )

        def mock_run(cmd, *args, **kwargs):
            return type("Result", (), {"returncode": 0, "stdout": b"<html>archived</html>"})()

        monkeypatch.setattr("subprocess.run", mock_run)

        class MockStorage:
            def save_file(self, uid, kind, filename, data):
                return f"{kind}/{filename}"

        monkeypatch.setattr(
            "fourdpocket.storage.local.LocalStorage",
            lambda: MockStorage(),
        )

        # Mock _update_item_archive to avoid DB call
        monkeypatch.setattr(
            "fourdpocket.workers.archiver._update_item_archive",
            lambda item_id, path: None,
        )

        result = archive_page.call_local(str(item.id), "https://example.com/article", str(user.id))
        assert result["status"] == "success"
        assert result["method"] == "monolith"

    def test_archive_page_monolith_timeout_falls_back_to_playwright(self, db: Session, engine, monkeypatch):
        """monolith timeout triggers playwright fallback."""
        import subprocess

        import fourdpocket.db.session as db_module

        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_archiver_user(db)
        item = _make_archiver_item(db, user)

        call_count = [0]

        def mock_which(name):
            return "/usr/bin/monolith" if name == "monolith" else None

        def mock_run(cmd, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise subprocess.TimeoutExpired(cmd, 60)
            return type("Result", (), {"returncode": 0, "stdout": b"<html>fallback</html>"})()

        monkeypatch.setattr("shutil.which", mock_which)
        monkeypatch.setattr("subprocess.run", mock_run)

        # Mock playwright async flow
        class MockPage:
            async def goto(self, url, **kwargs):
                pass

            async def content(self):
                return "<html>fallback</html>"

        class MockBrowser:
            async def close(self):
                pass

        class MockBrowserInstance:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def new_page(self):
                return MockPage()

            async def close(self):
                pass

        class MockChromium:
            async def launch(self, headless=True):
                return MockBrowserInstance()

        class MockPlaywright:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            chromium = MockChromium()

        def mock_asyncio_run(coro):
            # Run the async playwright coroutine in-place
            try:
                import asyncio
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)

        monkeypatch.setattr(
            "asyncio.run",
            mock_asyncio_run,
        )
        monkeypatch.setattr(
            "playwright.async_api.async_playwright",
            lambda: MockPlaywright(),
        )

        class MockStorage:
            def save_file(self, uid, kind, filename, data):
                return f"{kind}/{filename}"

        monkeypatch.setattr(
            "fourdpocket.storage.local.LocalStorage",
            lambda: MockStorage(),
        )

        monkeypatch.setattr(
            "fourdpocket.workers.archiver._update_item_archive",
            lambda item_id, path: None,
        )

        result = archive_page.call_local(str(item.id), "https://example.com/article", str(user.id))
        # After monolith timeout, playwright fallback succeeds
        assert result["status"] == "success"
        assert result["method"] == "playwright"


class TestUpdateItemArchive:
    """Test the _update_item_archive helper."""

    def test_updates_archive_path(self, db: Session, engine, monkeypatch):
        """archive_path is set and committed to DB."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_archiver_user(db)

        item = KnowledgeItem(
            user_id=user.id,
            title="Archive Path Test",
            archive_path=None,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        _update_item_archive(str(item.id), "archives/test.html")

        db.refresh(item)
        assert item.archive_path == "archives/test.html"
