"""Background task for page screenshot capture."""

import logging
import uuid

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.task(retries=2, retry_delay=15)
def capture_screenshot(item_id: str, url: str, user_id: str) -> dict:
    """Capture a full-page screenshot using Playwright."""
    from fourdpocket.storage.local import LocalStorage

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
