"""Substack processor — extract articles via httpx + readability."""

import logging
import re

import httpx
from readability import Document

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


def _extract_newsletter_name(url: str) -> str | None:
    match = re.match(r"https?://([^.]+)\.substack\.com", url)
    return match.group(1) if match else None


@register_processor
class SubstackProcessor(BaseProcessor):
    """Extract Substack articles using readability."""

    url_patterns = [r"[a-z0-9-]+\.substack\.com/p/"]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        try:
            response = await self._fetch_url(url, timeout=15)
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="substack",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="substack",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        raw_html = response.text
        og_meta = self._extract_og_metadata(raw_html)

        try:
            doc = Document(raw_html)
            readable_title = doc.title()
            readable_content = doc.summary()
        except Exception:
            readable_title = None
            readable_content = None

        title = (
            og_meta.get("og_title")
            or readable_title
            or og_meta.get("html_title")
            or url
        )
        description = og_meta.get("og_description") or og_meta.get("description")
        author = og_meta.get("author") or og_meta.get("og_article:author")
        newsletter_name = _extract_newsletter_name(url)

        media = []
        og_image = og_meta.get("og_image")
        if og_image:
            media.append({"type": "image", "url": og_image, "role": "thumbnail"})

        metadata = {
            "url": url,
            "author": author,
            "newsletter_name": newsletter_name,
        }
        if og_meta.get("og_site_name"):
            metadata["site_name"] = og_meta["og_site_name"]

        return ProcessorResult(
            title=title,
            description=description,
            content=readable_content,
            raw_content=raw_html[:100000],
            media=media,
            metadata=metadata,
            source_platform="substack",
            item_type="url",
            status=ProcessorStatus.success,
        )
