"""Threads (Meta) processor — best-effort public extraction (Phase 4d).

Threads has no public read API without OAuth. The unfurl preview HTML
is what we can rely on. Strategy mirrors LinkedIn/Instagram:

  1. Fetch with a real Chromium UA (Meta serves a sparse HTML to
     library UAs).
  2. OG metadata is the floor (title + description + thumbnail).
  3. trafilatura on the HTML — Threads does ship a fair amount of post
     text in the public preview when the post isn't reply-gated.
  4. Be honest about limited extraction.
"""

from __future__ import annotations

import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)

_AUTHOR_PATTERN = re.compile(r"threads\.net/@([^/?#]+)", re.IGNORECASE)
_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


@register_processor
class ThreadsProcessor(BaseProcessor):
    """Threads post → typed sections."""

    url_patterns = [
        r"threads\.net/@",
    ]
    priority = 8

    async def _fetch_with_browser_ua(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(
                timeout=15, follow_redirects=True,
                headers={
                    "User-Agent": _CHROME_UA,
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.5",
                },
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.text
        except Exception as e:
            logger.debug("Threads fetch %s failed: %s", url, e)
            return None

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        html = await self._fetch_with_browser_ua(url)
        if html is None:
            return ProcessorResult(
                title=url, source_platform="threads",
                status=ProcessorStatus.partial,
                error="Threads returned no readable HTML",
                metadata={"url": url, "limited_extraction": True},
            )

        og = self._extract_og_metadata(html)
        title = og.get("og_title") or og.get("html_title") or url
        og_desc = og.get("og_description") or og.get("description") or ""
        thumb = og.get("og_image")

        # Extract author from URL path (more reliable than OG)
        author_match = _AUTHOR_PATTERN.search(url)
        author = author_match.group(1) if author_match else og.get("author", "")

        # Body: try trafilatura, fall back to OG description
        body_text = ""
        try:
            import trafilatura  # type: ignore
            body_text = trafilatura.extract(
                html, output_format="markdown",
                include_comments=False, favor_recall=True,
                url=url,
            ) or ""
        except Exception as e:
            logger.debug("trafilatura failed for %s: %s", url, e)

        if len(body_text.strip()) < 50 and len(og_desc) > len(body_text):
            body_text = og_desc

        body_text = body_text.strip()
        limited = len(body_text) < 30

        # ─── Sections ───
        sections: list[Section] = []
        order = 0
        sections.append(Section(
            id=make_section_id(url, order), kind="title", order=order,
            role="main", text=title,
        ))
        order += 1

        if body_text:
            sections.append(Section(
                id=make_section_id(url, order), kind="post", order=order,
                role="main", text=body_text,
                author=author or None,
                source_url=url,
            ))
            order += 1

        if limited:
            sections.append(Section(
                id=make_section_id(url, order), kind="metadata_block",
                order=order, role="supplemental",
                text=(
                    "Limited Threads preview — full conversation requires "
                    "sign-in via the Meta Threads API."
                ),
            ))
            order += 1

        media: list[dict] = []
        if thumb:
            media.append({"type": "image", "url": thumb, "role": "thumbnail"})

        metadata = {
            "url": url,
            "author": author,
            "limited_extraction": limited,
            "extracted_chars": len(body_text),
        }
        if og.get("og_site_name"):
            metadata["site_name"] = og["og_site_name"]

        status = ProcessorStatus.success if not limited else ProcessorStatus.partial

        return ProcessorResult(
            title=title,
            description=(body_text or og_desc)[:300] or None,
            content=None,
            raw_content=html[:100000],
            media=media,
            metadata=metadata,
            source_platform="threads",
            item_type="url",
            status=status,
            error="Limited Threads preview" if limited else None,
            sections=sections,
        )
