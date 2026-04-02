"""Background task for page screenshot capture."""

import ipaddress
import logging
import socket
import uuid
from urllib.parse import urlparse

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)

MAX_SCREENSHOT_BYTES = 10 * 1024 * 1024  # 10MB

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_screenshot_url(url: str) -> bool:
    """Check if URL is safe for screenshot capture (SSRF protection)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in addr_info:
                ip = ipaddress.ip_address(sockaddr[0])
                for network in _BLOCKED_NETWORKS:
                    if ip in network:
                        return False
        except socket.gaierror:
            return False
        return True
    except Exception:
        return False


@huey.task(retries=2, retry_delay=15)
def capture_screenshot(item_id: str, url: str, user_id: str) -> dict:
    """Capture a full-page screenshot using Playwright."""
    from fourdpocket.storage.local import LocalStorage

    # SSRF protection: validate URL before navigating
    if not _is_safe_screenshot_url(url):
        logger.warning("SSRF blocked for screenshot: %s", url)
        return {"status": "error", "error": "URL blocked: targets internal network"}

    logger.info("Capturing screenshot of %s for item %s", url, item_id)
    storage = LocalStorage()
    uid = uuid.UUID(user_id)
    filename = f"{item_id}.png"

    try:
        import asyncio

        from playwright.async_api import async_playwright

        async def _capture():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 720})
                await page.goto(url, timeout=30000, wait_until="networkidle")
                screenshot_bytes = await page.screenshot(full_page=True, type="png")
                await browser.close()
                return screenshot_bytes

        png_bytes = asyncio.run(_capture())
        if png_bytes:
            if len(png_bytes) > MAX_SCREENSHOT_BYTES:
                logger.warning(
                    "Screenshot too large (%d > %d bytes): %s",
                    len(png_bytes),
                    MAX_SCREENSHOT_BYTES,
                    url,
                )
                return {"status": "error", "error": "Screenshot exceeds maximum size limit"}
            relative_path = storage.save_file(uid, "screenshots", filename, png_bytes)
            _update_item_screenshot(item_id, relative_path)
            logger.info("Screenshot captured for %s", url)
            return {"status": "success", "path": relative_path}

    except ImportError:
        logger.debug("Playwright not installed, skipping screenshot")
        return {"status": "skipped", "reason": "Playwright not installed"}
    except Exception as e:
        logger.warning("Screenshot capture failed for %s: %s", url, e)
        return {"status": "error", "error": str(e)[:200]}

    return {"status": "error", "error": "Screenshot capture produced no data"}


def _update_item_screenshot(item_id: str, screenshot_path: str) -> None:
    """Update item's screenshot_path in database."""
    from sqlmodel import Session

    from fourdpocket.db.session import get_engine
    from fourdpocket.models.item import KnowledgeItem

    engine = get_engine()
    with Session(engine) as db:
        item = db.get(KnowledgeItem, uuid.UUID(item_id))
        if item:
            item.screenshot_path = screenshot_path
            db.add(item)
            db.commit()
