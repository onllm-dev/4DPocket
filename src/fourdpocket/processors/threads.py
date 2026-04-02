"""Threads processor - extract posts via OG metadata scraping."""

import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)

_AUTHOR_PATTERN = re.compile(r"threads\.net/@([^/?#]+)", re.IGNORECASE)


@register_processor
class ThreadsProcessor(BaseProcessor):
    """Extract Threads posts via Open Graph metadata."""

    url_patterns = [
        r"threads\.net/@",
    ]
    priority = 8

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        try:
            response = await self._fetch_url(url, timeout=15)
            html_content = response.text
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="threads",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="threads",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        og = self._extract_og_metadata(html_content)

        title = og.get("og_title") or og.get("html_title") or url
        description = og.get("og_description") or og.get("description")
        thumbnail_url = og.get("og_image")

        # Extract author from URL path
        author_match = _AUTHOR_PATTERN.search(url)
        author = author_match.group(1) if author_match else og.get("author", "")

        media = []
        if thumbnail_url:
            media.append({"type": "image", "url": thumbnail_url, "role": "thumbnail"})

        metadata = {
            "url": url,
            "author": author,
        }

        return ProcessorResult(
            title=title,
            description=description,
            media=media,
            metadata=metadata,
            source_platform="threads",
            item_type="url",
            status=ProcessorStatus.success if (title and description) else ProcessorStatus.partial,
        )
