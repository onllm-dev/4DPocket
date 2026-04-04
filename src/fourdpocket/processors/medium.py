"""Medium processor - extract articles via JSON API + readability fallback."""

import json
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
    match = re.match(r"https?://([^/]+)\.medium\.com", url)
    if match:
        return match.group(1)
    return None


def _try_json_endpoint(url: str) -> dict | None:
    """Try Medium's hidden JSON endpoint for reliable content extraction.

    Medium prefixes JSON responses with `])}while(1);</x>` to prevent JSONP abuse.
    """
    from fourdpocket.processors.base import _is_safe_url

    json_url = url.rstrip("/") + "?format=json"
    if not _is_safe_url(json_url):
        return None
    try:
        resp = httpx.get(
            json_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; 4DPocket/1.0)",
                "Accept": "application/json",
            },
            follow_redirects=False,
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        text = resp.text
        # Strip Medium's anti-JSONP prefix
        if text.startswith("])}while(1);</x>"):
            text = text[len("])}while(1);</x>"):]

        data = json.loads(text)
        return data.get("payload", {})
    except Exception as e:
        logger.debug("Medium JSON endpoint failed for %s: %s", url, e)
        return None


def _extract_from_json(payload: dict) -> dict:
    """Extract article data from Medium's JSON payload."""
    post = payload.get("value", {})
    if not post:
        return {}

    title = post.get("title", "")
    subtitle = post.get("content", {}).get("subtitle", "")

    # Extract paragraphs from the post content
    paragraphs = post.get("content", {}).get("bodyModel", {}).get("paragraphs", [])
    content_parts = []
    for p in paragraphs:
        text = p.get("text", "")
        if text:
            p_type = p.get("type")
            if p_type == 3:  # H3 heading
                content_parts.append(f"\n### {text}\n")
            elif p_type == 6:  # blockquote
                content_parts.append(f"> {text}")
            elif p_type == 8:  # code block
                content_parts.append(f"```\n{text}\n```")
            elif p_type == 13:  # H4 heading
                content_parts.append(f"\n#### {text}\n")
            else:
                content_parts.append(text)

    # Extract author
    creator_id = post.get("creatorId", "")
    references = payload.get("references", {})
    user_data = references.get("User", {}).get(creator_id, {})
    author = user_data.get("name", "")

    # Extract metadata
    clap_count = post.get("virtuals", {}).get("totalClapCount", 0)
    reading_time = post.get("virtuals", {}).get("readingTime", 0)
    word_count = post.get("virtuals", {}).get("wordCount", 0)
    published_at = post.get("firstPublishedAt")

    # Extract tags
    tags = [t.get("slug", "") for t in post.get("virtuals", {}).get("tags", [])]

    # Cover image
    preview_image = post.get("virtuals", {}).get("previewImage", {})
    image_id = preview_image.get("imageId", "")
    cover_url = f"https://miro.medium.com/v2/resize:fit:1200/{image_id}" if image_id else None

    return {
        "title": title,
        "subtitle": subtitle,
        "content": "\n\n".join(content_parts),
        "author": author,
        "clap_count": clap_count,
        "reading_time": round(reading_time, 1),
        "word_count": word_count,
        "published_at": published_at,
        "tags": tags,
        "cover_url": cover_url,
    }


@register_processor
class MediumProcessor(BaseProcessor):
    """Extract Medium articles using JSON API with readability fallback."""

    url_patterns = [
        r"medium\.com/",
        r"[a-z0-9-]+\.medium\.com/",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        # Try JSON endpoint first (more reliable than HTML scraping)
        payload = _try_json_endpoint(url)
        if payload:
            extracted = _extract_from_json(payload)
            if extracted.get("content"):
                media = []
                if extracted.get("cover_url"):
                    media.append({"type": "image", "url": extracted["cover_url"], "role": "thumbnail"})

                metadata = {
                    "url": url,
                    "author": extracted.get("author"),
                    "clap_count": extracted.get("clap_count"),
                    "reading_time_min": extracted.get("reading_time"),
                    "word_count": extracted.get("word_count"),
                    "tags": extracted.get("tags", []),
                    "published_at": extracted.get("published_at"),
                }

                description = extracted.get("subtitle") or (extracted["content"][:300] if extracted.get("content") else None)

                return ProcessorResult(
                    title=extracted.get("title") or url,
                    description=description,
                    content=extracted["content"],
                    media=media,
                    metadata=metadata,
                    source_platform="medium",
                    item_type="url",
                    status=ProcessorStatus.success,
                )

        # Fallback to HTML + readability
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
