"""TikTok processor — extract video metadata via yt-dlp."""

import logging

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


@register_processor
class TikTokProcessor(BaseProcessor):
    """Extract TikTok video metadata using yt-dlp."""

    url_patterns = [
        r"tiktok\.com/@[^/]+/video/",
        r"vm\.tiktok\.com/",
        r"tiktok\.com/t/",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        try:
            import yt_dlp
        except ImportError:
            return ProcessorResult(
                title=url,
                source_platform="tiktok",
                status=ProcessorStatus.failed,
                error="yt-dlp not installed",
                metadata={"url": url},
            )

        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="tiktok",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        if not info:
            return ProcessorResult(
                title=url,
                source_platform="tiktok",
                status=ProcessorStatus.failed,
                error="yt-dlp returned no info",
                metadata={"url": url},
            )

        title = info.get("title") or info.get("description") or url
        description = info.get("description", "")
        author = info.get("uploader") or info.get("creator") or info.get("channel", "")
        view_count = info.get("view_count")
        thumbnail_url = info.get("thumbnail")

        # Hashtags from tags or description
        hashtags = info.get("tags", [])

        media = []
        if thumbnail_url:
            media.append({"type": "image", "url": thumbnail_url, "role": "thumbnail"})

        metadata = {
            "url": url,
            "author": author,
            "view_count": view_count,
            "like_count": info.get("like_count"),
            "repost_count": info.get("repost_count"),
            "comment_count": info.get("comment_count"),
            "upload_date": info.get("upload_date"),
            "hashtags": hashtags,
            "duration": info.get("duration"),
        }

        return ProcessorResult(
            title=title,
            description=description[:300] if description else None,
            content=description if description else None,
            media=media,
            metadata=metadata,
            source_platform="tiktok",
            item_type="url",
            status=ProcessorStatus.success,
        )
