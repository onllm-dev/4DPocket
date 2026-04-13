"""Substack processor — newsletter post extraction.

Per R&D memo: Substack exposes a per-publication API
``https://{pub}.substack.com/api/v1/posts/{slug}`` that returns
``body_html`` cleanly. Try that first; fall back to trafilatura on the
HTML page; final fallback to readability + OG metadata.
"""

from __future__ import annotations

import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)


def _extract_pub_and_slug(url: str) -> tuple[str | None, str | None]:
    m = re.match(r"https?://([^.]+)\.substack\.com/p/([\w\-]+)", url)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def _try_substack_api(pub: str, slug: str) -> dict | None:
    api_url = f"https://{pub}.substack.com/api/v1/posts/{slug}"
    try:
        r = httpx.get(
            api_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; 4dpocket/0.2)",
                "Accept": "application/json",
            },
            timeout=15, follow_redirects=True,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.debug("Substack API failed for %s/%s: %s", pub, slug, e)
    return None


def _html_to_sections(html: str, url: str, start_order: int) -> tuple[list[Section], int]:
    """Parse Substack body_html into typed sections."""
    from lxml import html as lxml_html

    sections: list[Section] = []
    order = start_order
    try:
        doc = lxml_html.fromstring(html)
    except Exception:
        return sections, order

    for el in doc.iter():
        tag = (el.tag or "").lower()
        text = (el.text_content() or "").strip()
        if not text:
            continue
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            depth = int(tag[1]) - 1
            sections.append(Section(
                id=make_section_id(url, order), kind="heading", order=order,
                depth=depth, role="main", text=text,
            ))
            order += 1
        elif tag == "p":
            sections.append(Section(
                id=make_section_id(url, order), kind="paragraph", order=order,
                role="main", text=text,
            ))
            order += 1
        elif tag == "blockquote":
            sections.append(Section(
                id=make_section_id(url, order), kind="quote", order=order,
                role="main", text=text,
            ))
            order += 1
        elif tag in ("pre", "code") and len(text) > 20:
            sections.append(Section(
                id=make_section_id(url, order), kind="code", order=order,
                role="main", text=text,
            ))
            order += 1
        elif tag == "li":
            sections.append(Section(
                id=make_section_id(url, order), kind="list_item", order=order,
                role="main", text=text,
            ))
            order += 1
    return sections, order


@register_processor
class SubstackProcessor(BaseProcessor):
    """Substack post → typed sections via API; trafilatura fallback."""

    url_patterns = [r"[a-z0-9-]+\.substack\.com/p/"]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        pub, slug = _extract_pub_and_slug(url)

        # ─── Path 1: Substack API ───
        api_data: dict | None = None
        if pub and slug:
            api_data = _try_substack_api(pub, slug)

        if api_data:
            title = api_data.get("title") or url
            subtitle = api_data.get("subtitle") or ""
            body_html = api_data.get("body_html") or ""
            cover = api_data.get("cover_image") or api_data.get("og_image")

            sections: list[Section] = []
            order = 0
            if title:
                sections.append(Section(
                    id=make_section_id(url, order), kind="title", order=order,
                    role="main", text=title,
                ))
                order += 1
            if subtitle:
                sections.append(Section(
                    id=make_section_id(url, order), kind="subtitle", order=order,
                    role="main", text=subtitle,
                ))
                order += 1
            body_sections, order = _html_to_sections(body_html, url, order)
            sections.extend(body_sections)

            media = []
            if cover:
                media.append({"type": "image", "url": cover, "role": "thumbnail"})

            authors = api_data.get("publishedBylines") or []
            author_name = ", ".join(
                a.get("name", "") for a in authors if a.get("name")
            ) or None

            metadata = {
                "url": url,
                "author": author_name,
                "newsletter_name": pub,
                "publication": pub,
                "subtitle": subtitle,
                "published_at": api_data.get("post_date"),
                "reactions": api_data.get("reactions"),
                "comment_count": api_data.get("comment_count"),
                "word_count": api_data.get("wordcount"),
            }
            if api_data.get("postTags"):
                metadata["tags"] = [
                    t.get("name", "") for t in api_data["postTags"] if t.get("name")
                ]

            return ProcessorResult(
                title=title,
                description=subtitle or None,
                content=None,
                media=media,
                metadata=metadata,
                source_platform="substack",
                item_type="url",
                status=ProcessorStatus.success,
                sections=sections,
            )

        # ─── Path 2: HTML + trafilatura/readability ───
        try:
            response = await self._fetch_url(url, timeout=15)
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url, source_platform="substack",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url, source_platform="substack",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        raw_html = response.text
        og_meta = self._extract_og_metadata(raw_html)

        from fourdpocket.processors.medium import _trafilatura_or_readability_sections

        sections = _trafilatura_or_readability_sections(raw_html, url, og_meta)

        title = og_meta.get("og_title") or og_meta.get("html_title") or url
        description = og_meta.get("og_description") or og_meta.get("description")
        media = []
        if og_meta.get("og_image"):
            media.append({"type": "image", "url": og_meta["og_image"], "role": "thumbnail"})
        metadata = {
            "url": url,
            "author": og_meta.get("author") or og_meta.get("og_article:author"),
            "newsletter_name": pub,
        }
        if og_meta.get("og_site_name"):
            metadata["site_name"] = og_meta["og_site_name"]

        return ProcessorResult(
            title=title,
            description=description,
            content=None,
            raw_content=raw_html[:100000],
            media=media,
            metadata=metadata,
            source_platform="substack",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
