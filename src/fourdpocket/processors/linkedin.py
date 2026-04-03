"""LinkedIn processor - extract public posts and articles via httpx + readability."""

import logging

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


@register_processor
class LinkedInProcessor(BaseProcessor):
    """Extract LinkedIn public posts and pulse articles."""

    url_patterns = [
        r"linkedin\.com/posts/",
        r"linkedin\.com/pulse/",
    ]
    priority = 8

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        try:
            response = await self._fetch_url(url, timeout=15)
            html_content = response.text
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="linkedin",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="linkedin",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        try:
            from readability import Document
            doc = Document(html_content)
            title = doc.title() or url
            content = doc.summary()
            # Strip residual HTML tags from readability output
            og = self._extract_og_metadata(html_content)
            description = og.get("og_description") or og.get("description")
            author = og.get("author") or og.get("og_site_name")
            thumbnail_url = og.get("og_image")
        except Exception:
            og = self._extract_og_metadata(html_content)
            title = og.get("og_title") or og.get("html_title") or url
            content = None
            description = og.get("og_description") or og.get("description")
            author = og.get("author") or og.get("og_site_name")
            thumbnail_url = og.get("og_image")

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
            content=content,
            media=media,
            metadata=metadata,
            source_platform="linkedin",
            item_type="url",
            status=ProcessorStatus.success if content else ProcessorStatus.partial,
        )
