"""Medium processor — extract articles via httpx + readability."""

import logging
import re

import httpx
from readability import Document

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


def _extract_publication(url: str, og_meta: dict) -> str | None:
    """Try to get publication name from OG metadata or subdomain."""
    if og_meta.get("og_site_name"):
        return og_meta["og_site_name"]
    # Custom subdomain like pub.medium.com or custom domain
    match = re.match(r"https?://([^/]+)\.medium\.com", url)
    if match:
        return match.group(1)
    return None


@register_processor
class MediumProcessor(BaseProcessor):
    """Extract Medium articles using readability."""

    url_patterns = [
        r"medium\.com/",
        r"[a-z0-9-]+\.medium\.com/",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        try:
            response = await self._fetch_url(url, timeout=15)
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="medium",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="medium",
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
        author = og_meta.get("author")
        publication = _extract_publication(url, og_meta)

        media = []
        og_image = og_meta.get("og_image")
        if og_image:
            media.append({"type": "image", "url": og_image, "role": "thumbnail"})

        metadata = {
            "url": url,
            "author": author,
            "publication": publication,
        }
        if og_meta.get("keywords"):
            metadata["keywords"] = og_meta["keywords"]

        return ProcessorResult(
            title=title,
            description=description,
            content=readable_content,
            raw_content=raw_html[:100000],
            media=media,
            metadata=metadata,
            source_platform="medium",
            item_type="url",
            status=ProcessorStatus.success,
        )
