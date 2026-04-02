"""Generic URL processor - fallback for any URL."""

import httpx
from readability import Document

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor


@register_processor
class GenericURLProcessor(BaseProcessor):
    """Extract content from any URL using readability and metadata parsing."""

    url_patterns = []  # matches nothing - used as fallback
    priority = -1  # lowest priority

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        try:
            response = await self._fetch_url(url)
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="generic",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}: {str(e)[:200]}",
                metadata={"url": url},
            )
        except (httpx.RequestError, httpx.TimeoutException) as e:
            return ProcessorResult(
                title=url,
                source_platform="generic",
                status=ProcessorStatus.failed,
                error=f"Request failed: {str(e)[:200]}",
                metadata={"url": url},
            )

        content_type = response.headers.get("content-type", "")
        raw_html = response.text

        # Non-HTML content - just save metadata
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return ProcessorResult(
                title=url,
                description=f"Non-HTML content: {content_type}",
                source_platform="generic",
                metadata={"url": url, "content_type": content_type},
                status=ProcessorStatus.partial,
            )

        # Extract readable content via readability
        try:
            doc = Document(raw_html)
            readable_title = doc.title()
            readable_content = doc.summary()
            readable_short = doc.short_title()
        except Exception:
            readable_title = None
            readable_content = None
            readable_short = None

        # Extract OG metadata
        og_meta = self._extract_og_metadata(raw_html)

        # Determine best title
        title = (
            og_meta.get("og_title")
            or readable_title
            or og_meta.get("html_title")
            or url
        )

        # Determine description
        description = og_meta.get("og_description") or og_meta.get("description")

        # Build media list from OG image
        media = []
        og_image = og_meta.get("og_image")
        if og_image:
            media.append({"type": "image", "url": og_image, "role": "thumbnail"})

        # Build metadata dict
        metadata = {
            "url": url,
            "content_type": content_type,
            "status_code": response.status_code,
        }
        if og_meta.get("favicon"):
            metadata["favicon"] = og_meta["favicon"]
        if og_meta.get("author"):
            metadata["author"] = og_meta["author"]
        if og_meta.get("keywords"):
            metadata["keywords"] = og_meta["keywords"]
        if og_meta.get("og_site_name"):
            metadata["site_name"] = og_meta["og_site_name"]
        if og_meta.get("og_type"):
            metadata["og_type"] = og_meta["og_type"]
        if og_meta.get("json_ld_raw"):
            metadata["json_ld"] = og_meta["json_ld_raw"][:5000]  # cap size

        return ProcessorResult(
            title=title,
            description=description,
            content=readable_content,
            raw_content=raw_html[:100000],  # cap raw HTML at 100KB
            media=media,
            metadata=metadata,
            source_platform="generic",
            item_type="url",
            status=ProcessorStatus.success,
        )
