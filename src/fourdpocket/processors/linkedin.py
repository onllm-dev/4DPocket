"""LinkedIn processor — best-effort public extraction.

LinkedIn actively blocks scraping; the public preview HTML is what we
get without auth. Strategy per the Phase 4a R&D memo:

  1. Use a real-browser User-Agent (LinkedIn serves a sparse public
     preview to library UAs, gives more to a Chromium UA).
  2. Trafilatura first (handles LinkedIn's JSON-in-script-tag pattern
     for /pulse/ articles). Falls back to readability for posts where
     trafilatura returns less than a paragraph.
  3. OG metadata as floor — gives us author, description, image even
     when the body is empty.

Honest about the ceiling: when extraction yields very little (typical
for /posts/ permalinks behind a sign-in wall) we mark the result
``partial`` and add a ``metadata_block`` section explaining the
limitation so the UI can surface "limited extraction" rather than
silently looking broken.
"""

from __future__ import annotations

import logging

import httpx

from fourdpocket.processors.base import (
    BaseProcessor,
    ProcessorResult,
    ProcessorStatus,
    _is_safe_url,
)
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)

# Modern Chromium-like UA. LinkedIn returns more public content to this
# than to library-default UAs (they 401 generic httpx/python-requests).
_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_MIN_BODY_CHARS = 150  # below this we still ship but flag as limited


@register_processor
class LinkedInProcessor(BaseProcessor):
    """LinkedIn public posts + Pulse articles → typed sections."""

    url_patterns = [
        r"linkedin\.com/posts/",
        r"linkedin\.com/pulse/",
    ]
    priority = 8

    async def _fetch_with_browser_ua(self, url: str) -> str | None:
        """Fetch with a real-browser UA. LinkedIn blocks library UAs."""
        if not _is_safe_url(url):
            logger.debug("LinkedIn fetch blocked (SSRF): %s", url)
            return None
        try:
            async with httpx.AsyncClient(
                timeout=15, follow_redirects=False,
                headers={
                    "User-Agent": _CHROME_UA,
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;"
                        "q=0.9,image/avif,image/webp,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.5",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                },
            ) as client:
                current_url = url
                for _ in range(6):
                    r = await client.get(current_url)
                    if r.is_redirect:
                        location = r.headers.get("location", "")
                        if not location or not _is_safe_url(location):
                            logger.debug("LinkedIn redirect blocked (SSRF): %s", location)
                            return None
                        current_url = location
                    else:
                        r.raise_for_status()
                        return r.text
                return None
        except httpx.HTTPStatusError as e:
            logger.debug("LinkedIn fetch %s: HTTP %s", url, e.response.status_code)
            return None
        except Exception as e:
            logger.debug("LinkedIn fetch %s failed: %s", url, e)
            return None

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        html = await self._fetch_with_browser_ua(url)
        if html is None:
            return ProcessorResult(
                title=url, source_platform="linkedin",
                status=ProcessorStatus.partial,
                error="LinkedIn returned no readable HTML — auth wall or rate limit",
                metadata={"url": url, "limited_extraction": True},
            )

        og = self._extract_og_metadata(html)

        # ─── Body extraction: trafilatura → readability ───
        body_text = ""
        body_html = ""
        try:
            import trafilatura  # type: ignore

            body_text = trafilatura.extract(
                html,
                output_format="markdown",
                include_tables=False,
                include_comments=False,
                favor_recall=True,
                url=url,
            ) or ""
        except Exception as e:
            logger.debug("trafilatura failed for %s: %s", url, e)

        if len(body_text.strip()) < _MIN_BODY_CHARS:
            try:
                from readability import Document
                doc = Document(html)
                body_html = doc.summary() or ""
                if body_html:
                    import re
                    fallback_text = re.sub(r"<[^>]+>", "", body_html).strip()
                    if len(fallback_text) > len(body_text):
                        body_text = fallback_text
            except Exception as e:
                logger.debug("readability failed for %s: %s", url, e)

        # OG description as last-resort floor — LinkedIn often leaves a
        # truncated excerpt of the post here even when body extraction
        # returns nothing useful.
        og_desc = og.get("og_description") or og.get("description") or ""
        if len(body_text.strip()) < _MIN_BODY_CHARS and len(og_desc) > len(body_text):
            body_text = og_desc

        title = (
            og.get("og_title")
            or og.get("html_title")
            or url
        )
        author = og.get("author") or og.get("og_site_name")
        thumbnail = og.get("og_image")
        is_article = "/pulse/" in url

        # ─── Sections ───
        sections: list[Section] = []
        order = 0
        sections.append(Section(
            id=make_section_id(url, order), kind="title", order=order,
            role="main", text=title, source_url=url,
        ))
        order += 1

        body_text_clean = body_text.strip()
        limited = len(body_text_clean) < _MIN_BODY_CHARS

        if body_text_clean:
            if is_article:
                # Pulse articles are long-form: try to split markdown
                # headings out so the chunker preserves structure.
                from fourdpocket.processors.pdf import _split_markdown_into_sections
                body_sections, order = _split_markdown_into_sections(
                    body_text_clean, page_no=None, parent_id=None,
                    start_order=order,
                )
                sections.extend(body_sections)
            else:
                kind = "post"
                sections.append(Section(
                    id=make_section_id(url, order), kind=kind, order=order,
                    role="main", text=body_text_clean,
                    author=author,
                    raw_html=body_html or None,
                ))
                order += 1

        if limited:
            # Always honest — UI can render this as a "limited extraction"
            # note alongside the OG image.
            sections.append(Section(
                id=make_section_id(url, order), kind="metadata_block",
                order=order, role="supplemental",
                text=(
                    "LinkedIn returned a limited preview. Sign-in is "
                    "required to see the full content of this post."
                ),
            ))
            order += 1

        media: list[dict] = []
        if thumbnail:
            media.append({"type": "image", "url": thumbnail, "role": "thumbnail"})

        metadata = {
            "url": url,
            "author": author,
            "post_type": "article" if is_article else "post",
            "limited_extraction": limited,
            "extracted_chars": len(body_text_clean),
        }
        if og.get("og_site_name"):
            metadata["site_name"] = og["og_site_name"]

        status = ProcessorStatus.success if not limited else ProcessorStatus.partial
        error = None if not limited else "LinkedIn limited public preview"

        return ProcessorResult(
            title=title,
            description=og_desc[:300] if og_desc else None,
            content=None,
            raw_content=html[:100000] if html else None,
            media=media,
            metadata=metadata,
            source_platform="linkedin",
            item_type="url",
            status=status,
            error=error,
            sections=sections,
        )
