"""Spotify processor — extract track, album, and playlist metadata via oEmbed."""

import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)

_TYPE_PATTERN = re.compile(r"open\.spotify\.com/(track|album|playlist)/", re.IGNORECASE)


@register_processor
class SpotifyProcessor(BaseProcessor):
    """Extract Spotify metadata using the oEmbed endpoint (no auth required)."""

    url_patterns = [
        r"open\.spotify\.com/track/",
        r"open\.spotify\.com/album/",
        r"open\.spotify\.com/playlist/",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        oembed_url = f"https://open.spotify.com/oembed?url={url}"

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(oembed_url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="spotify",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="spotify",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        title = data.get("title", "")
        author = data.get("author_name", "")
        thumbnail_url = data.get("thumbnail_url", "")
        provider = data.get("provider_name", "Spotify")

        # Determine content type from URL
        type_match = _TYPE_PATTERN.search(url)
        item_subtype = type_match.group(1) if type_match else "track"

        media = []
        if thumbnail_url:
            media.append({"type": "image", "url": thumbnail_url, "role": "thumbnail"})

        metadata = {
            "url": url,
            "author": author,
            "provider": provider,
            "spotify_type": item_subtype,
            "thumbnail_url": thumbnail_url,
            "oembed_html": data.get("html", ""),
        }

        description = f"{item_subtype.capitalize()} by {author}" if author else item_subtype.capitalize()

        return ProcessorResult(
            title=title,
            description=description,
            media=media,
            metadata=metadata,
            source_platform="spotify",
            item_type="url",
            status=ProcessorStatus.success,
        )
