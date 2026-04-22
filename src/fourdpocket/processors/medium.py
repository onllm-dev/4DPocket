"""Medium processor — JSON endpoint with trafilatura fallback.

Per R&D memo: Medium's ``?format=json`` endpoint is the cleanest source
when it works (it strips the ``])}while(1);</x>`` anti-JSONP prefix
manually). Falls back to trafilatura (the empirical winner for HTML
article extraction) when JSON is blocked, then OG metadata.

Sections:
  * ``title`` — article title
  * ``subtitle`` — when present (Medium has dedicated field)
  * ``heading`` / ``paragraph`` / ``quote`` / ``code`` — per-paragraph
    structure derived from Medium's bodyModel paragraph types
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from readability import Document

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)

# Medium aggressively blocks non-browser UAs on both the JSON and
# HTML endpoints. A realistic Chrome UA is required.
_CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Medium paragraph type codes (from the bodyModel.paragraphs[] schema)
_PARA_TYPE = {
    1: ("paragraph", 0),
    2: ("paragraph", 0),  # P
    3: ("heading", 2),    # H3
    4: ("figure", 0),     # IMG
    6: ("quote", 0),      # blockquote
    7: ("quote", 0),      # pullquote
    8: ("code", 0),       # code block
    9: ("list_item", 0),  # ULI
    10: ("list_item", 0), # OLI
    11: ("figure", 0),    # IFRAME
    13: ("heading", 3),   # H4
    14: ("heading", 1),   # H2 (rare in Medium, but exists)
}


def _extract_publication(url: str, og_meta: dict) -> str | None:
    if og_meta.get("og_site_name"):
        return og_meta["og_site_name"]
    m = re.match(r"https?://([^/]+)\.medium\.com", url)
    return m.group(1) if m else None


def _extract_post_id(url: str) -> str | None:
    """Extract the hex post ID from a Medium URL (last segment after final dash)."""
    m = re.search(r"-([0-9a-f]{8,})(?:[/?#]|$)", url)
    return m.group(1) if m else None


def _try_internal_api(url: str) -> dict | None:
    """Try Medium's internal API with TLS fingerprint impersonation.

    Uses curl_cffi to impersonate Chrome's TLS handshake — Medium blocks
    requests based on TLS fingerprint, not just User-Agent.
    """
    post_id = _extract_post_id(url)
    if not post_id:
        return None
    try:
        from curl_cffi import requests as cffi_requests

        api_url = f"https://medium.com/_/api/posts/{post_id}"
        resp = cffi_requests.get(api_url, impersonate="chrome", headers={
            "Accept": "application/json",
            "Referer": "https://medium.com/",
        }, timeout=15)
        if resp.status_code != 200:
            return None
        text = resp.text
        # Strip CSRF prefix (variable format: ])}while(1);</x> or )]}'  )
        brace = text.find("{")
        if brace > 0:
            text = text[brace:]
        return json.loads(text).get("payload", {})
    except ImportError:
        logger.debug("curl_cffi not installed — skipping internal API for %s", url)
    except Exception as e:
        logger.debug("Medium internal API failed for %s: %s", url, e)
    return None


def _try_json_endpoint(url: str) -> dict | None:
    """Fallback: try the public ?format=json endpoint with Chrome UA.

    Attempts curl_cffi TLS impersonation first (Medium inspects TLS fingerprint);
    falls back to plain httpx if curl_cffi is unavailable.
    """
    from fourdpocket.processors.base import _is_safe_url

    json_url = url.rstrip("/") + "?format=json"
    if not _is_safe_url(json_url):
        return None

    _headers = {
        "User-Agent": _CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        from curl_cffi import requests as cffi_requests

        resp = cffi_requests.get(json_url, headers=_headers, impersonate="chrome", timeout=15)
        if resp.status_code != 200:
            return None
        text = resp.text
        if text.startswith("])}while(1);</x>"):
            text = text[len("])}while(1);</x>"):]
        return json.loads(text).get("payload", {})
    except ImportError:
        logger.debug("curl_cffi not installed — falling back to httpx for %s", url)
    except Exception as e:
        logger.debug("Medium JSON endpoint (curl_cffi) failed for %s: %s", url, e)
        return None

    try:
        resp = httpx.get(json_url, headers=_headers, follow_redirects=True, timeout=15)
        if resp.status_code != 200:
            return None
        text = resp.text
        if text.startswith("])}while(1);</x>"):
            text = text[len("])}while(1);</x>"):]
        return json.loads(text).get("payload", {})
    except Exception as e:
        logger.debug("Medium JSON endpoint (httpx) failed for %s: %s", url, e)
        return None


def _sections_from_medium_payload(payload: dict, url: str) -> tuple[list[Section], dict]:
    """Convert Medium's bodyModel into typed sections + metadata."""
    sections: list[Section] = []
    post = payload.get("value", {}) or {}
    if not post:
        return sections, {}

    title = post.get("title", "")
    subtitle = (post.get("content") or {}).get("subtitle", "")

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

    paragraphs = (
        ((post.get("content") or {}).get("bodyModel") or {}).get("paragraphs") or []
    )
    for p in paragraphs:
        text = (p.get("text") or "").strip()
        if not text:
            continue
        ptype = p.get("type")
        kind, depth = _PARA_TYPE.get(ptype, ("paragraph", 0))
        sec = Section(
            id=make_section_id(url, order), kind=kind, order=order,
            depth=depth, role="main", text=text,
            extra={"medium_p_type": ptype} if ptype is not None else {},
        )
        sections.append(sec)
        order += 1

    creator_id = post.get("creatorId") or ""
    user_data = (payload.get("references") or {}).get("User", {}).get(creator_id, {}) or {}
    author = user_data.get("name") or ""

    virtuals = post.get("virtuals", {}) or {}
    cover = virtuals.get("previewImage", {}) or {}
    image_id = cover.get("imageId") or ""
    cover_url = (
        f"https://miro.medium.com/v2/resize:fit:1200/{image_id}" if image_id else None
    )

    metadata = {
        "url": url,
        "author": author,
        "clap_count": virtuals.get("totalClapCount", 0),
        "reading_time_min": round(virtuals.get("readingTime", 0), 1),
        "word_count": virtuals.get("wordCount", 0),
        "tags": [t.get("slug", "") for t in virtuals.get("tags") or []],
        "published_at": post.get("firstPublishedAt"),
        "subtitle": subtitle,
        "cover_url": cover_url,
    }
    return sections, metadata


@register_processor
class MediumProcessor(BaseProcessor):
    """Extract a Medium article as typed sections."""

    url_patterns = [
        r"medium\.com/",
        r"[a-z0-9-]+\.medium\.com/",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        # ─── Path 1: internal API with TLS impersonation (most reliable) ───
        payload = _try_internal_api(url) or _try_json_endpoint(url)
        if payload:
            sections, metadata = _sections_from_medium_payload(payload, url)
            if sections:
                title_section = next((s for s in sections if s.kind == "title"), None)
                title = title_section.text if title_section else url
                media: list[dict] = []
                if metadata.get("cover_url"):
                    media.append({
                        "type": "image", "url": metadata["cover_url"],
                        "role": "thumbnail",
                    })
                description = metadata.get("subtitle") or (
                    next((s.text for s in sections if s.kind == "paragraph"), "")[:300]
                )
                return ProcessorResult(
                    title=title,
                    description=description,
                    content=None,
                    media=media,
                    metadata=metadata,
                    source_platform="medium",
                    item_type="url",
                    status=ProcessorStatus.success,
                    sections=sections,
                )

        # ─── Path 2: HTML + trafilatura/readability fallback ───
        # Use Chrome UA — Medium aggressively blocks bot-like UAs.
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": _CHROME_UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                })
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url, source_platform="medium",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url, source_platform="medium",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        raw_html = response.text
        og_meta = self._extract_og_metadata(raw_html)
        sections = _trafilatura_or_readability_sections(raw_html, url, og_meta)

        title = (
            og_meta.get("og_title")
            or og_meta.get("html_title")
            or url
        )
        description = og_meta.get("og_description") or og_meta.get("description")
        media: list[dict] = []
        if og_meta.get("og_image"):
            media.append({"type": "image", "url": og_meta["og_image"], "role": "thumbnail"})
        metadata = {
            "url": url,
            "author": og_meta.get("author"),
            "publication": _extract_publication(url, og_meta),
        }
        if og_meta.get("keywords"):
            metadata["keywords"] = og_meta["keywords"]

        return ProcessorResult(
            title=title,
            description=description,
            content=None,
            raw_content=raw_html[:100000],
            media=media,
            metadata=metadata,
            source_platform="medium",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )


def _trafilatura_or_readability_sections(
    raw_html: str, url: str, og_meta: dict,
) -> list[Section]:
    """Try trafilatura first, fall back to readability."""
    sections: list[Section] = []
    order = 0
    title_text = og_meta.get("og_title") or og_meta.get("html_title")
    if title_text:
        sections.append(Section(
            id=make_section_id(url, order), kind="title", order=order,
            role="main", text=title_text,
        ))
        order += 1

    extracted_text: str | None = None
    try:
        import trafilatura  # type: ignore

        extracted_text = trafilatura.extract(
            raw_html,
            output_format="markdown",
            include_tables=True,
            include_comments=False,
            favor_recall=True,
            url=url,
        )
    except Exception as e:
        logger.debug("trafilatura failed for %s: %s", url, e)

    if extracted_text and len(extracted_text.strip()) >= 200:
        # Reuse the markdown→sections splitter from PDF (heading + paragraph)
        from fourdpocket.processors.pdf import _split_markdown_into_sections

        body_sections, _ = _split_markdown_into_sections(
            extracted_text, page_no=None, parent_id=None, start_order=order,
        )
        sections.extend(body_sections)
        return sections

    # Readability fallback (lower fidelity)
    try:
        doc = Document(raw_html)
        body = doc.summary() or ""
        if body.strip():
            sections.append(Section(
                id=make_section_id(url, order), kind="paragraph", order=order,
                role="main", text=re.sub(r"<[^>]+>", "", body).strip(),
                raw_html=body,
            ))
    except Exception as e:
        logger.debug("readability failed for %s: %s", url, e)

    return sections
