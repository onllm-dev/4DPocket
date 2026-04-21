"""Background task for downloading media files."""

import hashlib
import logging
import socket
import uuid
from urllib.parse import urlparse

import httpx

from fourdpocket.utils.ssrf import is_safe_url
from fourdpocket.workers import huey

logger = logging.getLogger(__name__)

MAX_MEDIA_SIZE_BYTES = 100 * 1024 * 1024  # 100MB


def _is_safe_media_url(url: str) -> bool:
    """Check if URL is safe to download (SSRF protection)."""
    return is_safe_url(url)


def _resolve_and_pin(url: str) -> str | None:
    """Resolve hostname to IP and return a pinned URL to prevent DNS rebinding.

    Returns the resolved IP as a string, or None if unsafe.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return None
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if not addr_info:
            return None
        resolved_ip = addr_info[0][4][0]
        if not is_safe_url(f"http://{resolved_ip}"):
            return None
        return resolved_ip
    except Exception:
        return None


@huey.task(retries=3, retry_delay=60)
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

        # SSRF protection: validate URL and pin DNS to prevent rebinding
        if not _is_safe_media_url(media_url):
            logger.warning("SSRF blocked: %s", media_url)
            continue

        try:
            # Follow redirects manually with per-hop SSRF + DNS pinning
            current_url = media_url
            final_url = None
            for _redirect in range(5):
                pinned_ip = _resolve_and_pin(current_url)
                if not pinned_ip:
                    logger.warning("SSRF blocked redirect: %s", current_url)
                    break
                resp = httpx.head(
                    current_url, timeout=10.0, follow_redirects=False,
                    headers={"User-Agent": "4DPocket/0.1"},
                )
                if resp.is_redirect:
                    current_url = resp.headers.get("location", "")
                    if not current_url:
                        break
                    continue
                final_url = current_url
                break

            if not final_url:
                logger.warning("Media redirect chain invalid: %s", media_url)
                continue

            # Final DNS pin check before streaming download
            if not _resolve_and_pin(final_url):
                logger.warning("SSRF blocked final URL: %s", final_url)
                continue

            with httpx.stream("GET", final_url, timeout=30.0, follow_redirects=False, headers={"User-Agent": "4DPocket/0.1"}) as response:
                response.raise_for_status()
                total_size = 0
                chunks = []
                for chunk in response.iter_bytes(chunk_size=65536):
                    total_size += len(chunk)
                    if total_size > MAX_MEDIA_SIZE_BYTES:
                        logger.warning(
                            "Media too large (>%dMB): %s",
                            MAX_MEDIA_SIZE_BYTES // (1024 * 1024),
                            media_url,
                        )
                        break
                    chunks.append(chunk)
                else:
                    # Only save if we didn't exceed the limit
                    media_bytes = b"".join(chunks)
                    url_hash = hashlib.sha256(media_url.encode()).hexdigest()[:12]
                    parsed_url = urlparse(media_url)
                    ext = parsed_url.path.rsplit(".", 1)[-1] if "." in parsed_url.path else "bin"
                    ext = ext[:10]
                    filename = f"{item_id}_{url_hash}.{ext}"

                    relative_path = storage.save_file(uid, "media", filename, media_bytes)
                    downloaded.append({
                        "original_url": media_url,
                        "local_path": relative_path,
                        "type": media_info.get("type", "unknown"),
                        "role": media_info.get("role", ""),
                        "size_bytes": total_size,
                    })

        except Exception as e:
            logger.warning("Failed to download media %s: %s", media_url, e)

    # Update item with local media paths (update existing entries, don't duplicate)
    if downloaded:
        engine = get_engine()
        with Session(engine) as db:
            item = db.get(KnowledgeItem, uuid.UUID(item_id))
            if item:
                existing_media = list(item.media) if item.media else []
                for dl in downloaded:
                    # Find existing entry by matching original URL or role
                    matched = False
                    for i, em in enumerate(existing_media):
                        if em.get("url") == dl.get("original_url") or (
                            em.get("role") == dl["role"] and em.get("role") in ("thumbnail",)
                        ):
                            existing_media[i] = {**em, **dl, "url": em.get("url", dl.get("original_url", ""))}
                            matched = True
                            break
                    if not matched:
                        existing_media.append(dl)
                item.media = existing_media
                db.add(item)
                db.commit()

    logger.info("Downloaded %d/%d media for item %s", len(downloaded), len(media_urls), item_id)
    return {"status": "success", "downloaded": len(downloaded), "total": len(media_urls)}


def download_video(url: str, output_dir: str, max_quality: str = "720") -> str | None:
    """Download video using yt-dlp. Returns output file path or None."""
    import subprocess
    from pathlib import Path

    if not _is_safe_media_url(url):
        logger.warning("SSRF blocked video download: %s", url)
        return None

    # Resolve URL through redirects with SSRF validation per hop before handing to yt-dlp
    try:
        current_url = url
        for _redirect in range(5):
            if not _is_safe_media_url(current_url):
                logger.warning("SSRF blocked video redirect: %s", current_url)
                return None
            resp = httpx.head(current_url, timeout=10.0, follow_redirects=False, headers={"User-Agent": "4DPocket/0.1"})
            if resp.is_redirect:
                current_url = resp.headers.get("location", "")
                if not current_url:
                    return None
                continue
            break
        # Final URL must also be safe
        if not _is_safe_media_url(current_url):
            logger.warning("SSRF blocked video final URL: %s", current_url)
            return None
    except Exception:
        return None

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_template = str(Path(output_dir) / "%(title)s.%(ext)s")

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--no-playlist",
                "-f", f"bestvideo[height<={max_quality}]+bestaudio/best[height<={max_quality}]",
                "--merge-output-format", "mp4",
                "-o", output_template,
                "--max-filesize", "500M",
                current_url,
            ],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            for f in Path(output_dir).glob("*.mp4"):
                return str(f)
        return None
    except Exception:
        return None
