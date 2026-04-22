"""Tests for the screenshot capture background task."""

import uuid

import pytest
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.workers.screenshot import (
    _is_safe_screenshot_url,
    _update_item_screenshot,
    capture_screenshot,
)


def _make_ss_user(db: Session):
    from fourdpocket.models.user import User

    user = User(
        email="ssuser@test.com",
        username="ssuser",
        password_hash="$2b$12$fake",
        display_name="Screenshot User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestIsSafeScreenshotUrl:
    """Test SSRF protection for screenshot URLs."""

    @pytest.mark.parametrize("url,expected", [
        ("https://example.com/page", True),
        ("http://example.com/page", True),
        ("https://127.0.0.1/page", False),
        ("https://10.0.0.1/page", False),
        ("https://172.16.0.1/page", False),
        ("https://192.168.1.1/page", False),
        ("https://169.254.0.1/page", False),
        ("file:///etc/passwd", False),
        ("javascript:alert(1)", False),
    ])
    def test_ssrf(self, url, expected):
        assert _is_safe_screenshot_url(url) == expected


class TestUpdateItemScreenshot:
    """Test the _update_item_screenshot helper."""

    def test_updates_screenshot_path(self, db: Session, engine, monkeypatch):
        """screenshot_path is set and committed to DB."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_ss_user(db)

        item = KnowledgeItem(
            user_id=user.id,
            title="Screenshot Path Test",
            screenshot_path=None,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        _update_item_screenshot(str(item.id), "screenshots/test.png")

        db.refresh(item)
        assert item.screenshot_path == "screenshots/test.png"


class TestCaptureScreenshot:
    """Test capture_screenshot task - success, errors, and edge cases."""

    def test_capture_screenshot_ssrf_blocked(self):
        """SSRF-protected URL returns error without attempting browser launch."""
        result = capture_screenshot.call_local(
            "550e8400-e29b-41d4-a716-446655440000",
            "https://127.0.0.1/admin",
            "550e8400-e29b-41d4-a716-446655440000",
        )
        assert result["status"] == "error"
        assert "internal network" in result["error"]

    def test_capture_screenshot_invalid_scheme(self):
        """Non-http/https scheme returns error."""
        result = capture_screenshot.call_local(
            "550e8400-e29b-41d4-a716-446655440000",
            "file:///etc/passwd",
            "550e8400-e29b-41d4-a716-446655440000",
        )
        assert result["status"] == "error"

    def test_capture_screenshot_missing_hostname(self):
        """URL with no hostname returns error."""
        result = capture_screenshot.call_local(
            "550e8400-e29b-41d4-a716-446655440000",
            "https:///path",
            "550e8400-e29b-41d4-a716-446655440000",
        )
        assert result["status"] == "error"

    def test_capture_screenshot_playwright_not_installed(self, db: Session, engine, monkeypatch):
        """ImportError from Playwright returns skipped status."""
        import fourdpocket.db.session as db_module
        monkeypatch.setattr(db_module, "_engine", engine)

        user = _make_ss_user(db)
        item = KnowledgeItem(user_id=user.id, title="No Playwright Test")
        db.add(item)
        db.commit()
        db.refresh(item)

        import sys

        # Block playwright import at sys.modules level so ImportError is raised
        sys.modules["playwright"] = None
        sys.modules["playwright.async_api"] = None

        try:
            result = capture_screenshot.call_local(
                str(item.id),
                "https://example.com/page",
                str(user.id),
            )
            assert result["status"] == "skipped"
            assert "not installed" in result["reason"]
        finally:
            # Clean up - just delete the keys we added
            for k in ["playwright", "playwright.async_api"]:
                sys.modules.pop(k, None)

    def test_capture_screenshot_exceeds_size_limit(self):
        """Screenshot size limit is MAX_SCREENSHOT_BYTES constant."""
        # Verify the constant is correctly set to 10MB
        from fourdpocket.workers.screenshot import MAX_SCREENSHOT_BYTES
        assert MAX_SCREENSHOT_BYTES == 10 * 1024 * 1024

    def test_is_safe_screenshot_url_ipv6_loopback(self):
        """IPv6 loopback addresses are blocked."""
        assert _is_safe_screenshot_url("https://[::1]/page") is False

    def test_is_safe_screenshot_url_ipv6_private(self):
        """IPv6 private addresses are blocked."""
        assert _is_safe_screenshot_url("https://[fc00::1]/page") is False

    def test_is_safe_screenshot_url_internal_hostname_resolves_to_blocked(self, monkeypatch):
        """Hostname resolving to internal IP is blocked."""
        import socket

        def fake_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            # Return a private IP for the given hostname
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 0))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

        assert _is_safe_screenshot_url("https://internal.example.com/page") is False

    def test_is_safe_screenshot_url_public_ip_allowed(self):
        """Public IP addresses are allowed."""
        # 8.8.8.8 is a public DNS server
        result = _is_safe_screenshot_url("https://8.8.8.8/")
        # Depends on actual resolution, but shouldn't be False due to internal block
        assert result is True

    # === PHASE 2B MOPUP ADDITIONS ===

    def test_is_safe_screenshot_url_blocked(self, monkeypatch):
        """Internal IP → False."""
        import socket

        def fake_getaddrinfo(*a):
            return [(2, 1, 6, '', ('127.0.0.1', 0))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

        from fourdpocket.workers.screenshot import _is_safe_screenshot_url
        assert _is_safe_screenshot_url("http://127.0.0.1/screenshot.png") is False

    def test_is_safe_screenshot_url_dns_fail(self, monkeypatch):
        """DNS failure → False."""
        import socket

        def fake_getaddrinfo(*a):
            raise socket.gaierror("DNS lookup failed")

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

        from fourdpocket.workers.screenshot import _is_safe_screenshot_url
        assert _is_safe_screenshot_url("http://example.com/screenshot.png") is False

    def test_capture_screenshot_success_via_mock(self, monkeypatch):
        """Playwright returns PNG bytes → success (mocked async chain).

        monkeypatch.setattr restores asyncio.run after the test, so this is
        safe in parallel runs (no cleanup leak unlike unittest.mock.patch).
        """
        import asyncio

        import fourdpocket.workers.screenshot as ss_module

        monkeypatch.setattr(asyncio, "run", lambda coro: b"\x89PNG\r\n\x1a\n" + b"fake_png_data")
        monkeypatch.setattr("fourdpocket.storage.local.LocalStorage.save_file", lambda *a, **kw: "screenshots/uuid.png")
        monkeypatch.setattr(ss_module, "_update_item_screenshot", lambda *a, **kw: None)

        result = ss_module.capture_screenshot.call_local(
            str(uuid.uuid4()),
            "https://example.com/page",
            str(uuid.uuid4()),
        )
        assert result["status"] == "success"
        assert "path" in result

    def test_capture_screenshot_size_exceeded_via_mock(self, monkeypatch):
        """PNG > 10MB → error status (mocked async chain).

        monkeypatch.setattr restores asyncio.run after the test.
        """
        import asyncio

        import fourdpocket.workers.screenshot as ss_module

        large_png = b"\x89PNG\r\n\x1a\n" + b"x" * (11 * 1024 * 1024)
        monkeypatch.setattr(asyncio, "run", lambda coro: large_png)

        result = ss_module.capture_screenshot.call_local(
            str(uuid.uuid4()),
            "https://example.com/large-page",
            str(uuid.uuid4()),
        )
        assert result["status"] == "error"
        assert "size" in result["error"].lower() or "exceed" in result["error"].lower()
