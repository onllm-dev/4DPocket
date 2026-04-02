"""Background task for page archival."""

import logging
import shutil
import subprocess
import uuid

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.task(retries=2, retry_delay=30)
def archive_page(item_id: str, url: str, user_id: str) -> dict:
    """Archive a web page as a single HTML file.

    Strategy:
    1. Try monolith (best quality, Rust binary)
    2. Fall back to Playwright page.content() with inline resources
    3. Skip with warning if neither available
    """
    from sqlmodel import Session

    from fourdpocket.db.session import get_engine
    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.storage.local import LocalStorage

    logger.info("Archiving page %s for item %s", url, item_id)
    storage = LocalStorage()
    uid = uuid.UUID(user_id)
    filename = f"{item_id}.html"

    # Strategy 1: monolith
    if shutil.which("monolith"):
        try:
            result = subprocess.run(
                ["monolith", url, "-o", "-"],
                capture_output=True,
                timeout=60,
            )
            if result.returncode == 0 and result.stdout:
                relative_path = storage.save_file(uid, "archives", filename, result.stdout)
                _update_item_archive(item_id, relative_path)
                logger.info("Archived %s via monolith", url)
                return {"status": "success", "method": "monolith", "path": relative_path}
        except subprocess.TimeoutExpired:
            logger.warning("monolith timed out for %s", url)
        except Exception as e:
            logger.warning("monolith failed for %s: %s", url, e)

    # Strategy 2: Playwright
    try:
        import asyncio

        from playwright.async_api import async_playwright

        async def _archive_with_playwright():
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=30000, wait_until="networkidle")
                content = await page.content()
                await browser.close()
                return content.encode("utf-8")

        html_bytes = asyncio.run(_archive_with_playwright())
        if html_bytes:
            relative_path = storage.save_file(uid, "archives", filename, html_bytes)
            _update_item_archive(item_id, relative_path)
            logger.info("Archived %s via Playwright", url)
            return {"status": "success", "method": "playwright", "path": relative_path}

    except ImportError:
        logger.debug("Playwright not available for archival")
    except Exception as e:
        logger.warning("Playwright archival failed for %s: %s", url, e)

    logger.warning("No archival method available for %s", url)
    return {"status": "skipped", "reason": "No archival tool available"}


def _update_item_archive(item_id: str, archive_path: str) -> None:
    """Update item's archive_path in database."""
    from sqlmodel import Session

    from fourdpocket.db.session import get_engine
    from fourdpocket.models.item import KnowledgeItem

    engine = get_engine()
    with Session(engine) as db:
        item = db.get(KnowledgeItem, uuid.UUID(item_id))
        if item:
            item.archive_path = archive_path
            db.add(item)
            db.commit()
