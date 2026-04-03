"""Background task for downloading media files."""

import hashlib
import ipaddress
import logging
import socket
import uuid
from urllib.parse import urlparse

import httpx

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)

MAX_MEDIA_SIZE_BYTES = 100 * 1024 * 1024  # 100MB

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_media_url(url: str) -> bool:
    """Check if URL is safe to download (SSRF protection)."""
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


@huey.task(retries=1, retry_delay=60)
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

        # SSRF protection: validate URL before fetching
        if not _is_safe_media_url(media_url):
            logger.warning("SSRF blocked: %s", media_url)
            continue

        try:
            with httpx.stream(
                media_url,
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "4DPocket/0.1"},
            ) as response:
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


def download_video(url: str, output_dir: str, max_quality: str = "720") -> str | None:
    """Download video using yt-dlp. Returns output file path or None."""
    import subprocess
    from pathlib import Path

    if not _is_safe_media_url(url):
        logger.warning("SSRF blocked video download: %s", url)
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
                url,
            ],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            for f in Path(output_dir).glob("*.mp4"):
                return str(f)
        return None
    except Exception:
        return None
