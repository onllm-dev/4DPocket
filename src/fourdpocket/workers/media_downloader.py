"""Background task for downloading media files."""

import hashlib
import logging
import uuid
from urllib.parse import urlparse

import httpx

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.task(retries=2, retry_delay=10)
def download_media(item_id: str, user_id: str, media_urls: list[dict]) -> dict:
    """Download media files (images, thumbnails) and store locally.

    Args:
        item_id: Knowledge item ID
        user_id: Owner user ID
        media_urls: List of {"url": str, "type": str, "role": str}
    """
    from sqlmodel import Session

    from fourdpocket.db.session import get_engine
    from fourdpocket.models.item import KnowledgeItem
    from fourdpocket.storage.local import LocalStorage

    logger.info("Downloading %d media files for item %s", len(media_urls), item_id)
    storage = LocalStorage()
    uid = uuid.UUID(user_id)
    downloaded = []

    for media_info in media_urls:
        media_url = media_info.get("url", "")
        if not media_url:
            continue

        try:
            response = httpx.get(
                media_url,
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "4DPocket/0.1"},
            )
            response.raise_for_status()

            # Generate filename from URL hash + extension
            url_hash = hashlib.sha256(media_url.encode()).hexdigest()[:12]
            parsed = urlparse(media_url)
            ext = parsed.path.rsplit(".", 1)[-1] if "." in parsed.path else "bin"
            ext = ext[:10]  # cap extension length
            filename = f"{item_id}_{url_hash}.{ext}"

            relative_path = storage.save_file(uid, "media", filename, response.content)
            downloaded.append({
                "original_url": media_url,
                "local_path": relative_path,
                "type": media_info.get("type", "unknown"),
                "role": media_info.get("role", ""),
                "size_bytes": len(response.content),
            })

        except Exception as e:
            logger.warning("Failed to download media %s: %s", media_url, e)

    # Update item with local media paths
    if downloaded:
        engine = get_engine()
        with Session(engine) as db:
            item = db.get(KnowledgeItem, uuid.UUID(item_id))
            if item:
                existing_media = list(item.media) if item.media else []
                item.media = existing_media + downloaded
                db.add(item)
                db.commit()

    logger.info("Downloaded %d/%d media for item %s", len(downloaded), len(media_urls), item_id)
    return {"status": "success", "downloaded": len(downloaded), "total": len(media_urls)}
