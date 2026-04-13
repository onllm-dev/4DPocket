"""Mastodon / Fediverse processor — full thread context via ActivityPub.

Phase 4e — Mastodon is the easy one: ActivityPub is open, every
instance ships ``/api/v1/statuses/{id}`` and
``/api/v1/statuses/{id}/context`` (ancestors + descendants) without
auth. We use both so the toot lands with its full reply tree.

Sections:
  * ``post``          — the main toot
  * ``reply[]``       — descendants (responses), parented by in_reply_to
  * ``reply[]``       — ancestors (the toot is a reply to context),
                         emitted before the post with depth indicating
                         distance from the main toot (negative depth)
  * ``visual_caption`` — alt text for each media attachment that has one
"""

from __future__ import annotations

import logging
import re
from html.parser import HTMLParser

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section

logger = logging.getLogger(__name__)


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "br"):
            self._parts.append("\n")

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _strip_html(html: str) -> str:
    s = _HTMLStripper()
    s.feed(html or "")
    return s.get_text()


_MAX_REPLIES = 30  # cap descendants to keep embedding cost sane


@register_processor
class MastodonProcessor(BaseProcessor):
    """Mastodon status + reply tree as sections."""

    url_patterns = [
        r"https?://[^/]+/@[^/]+/\d+",
    ]
    priority = 8

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        m = re.search(r"https?://([^/]+)/@[^/]+/(\d+)", url)
        if not m:
            return ProcessorResult(
                title=url, source_platform="mastodon",
                status=ProcessorStatus.failed,
                error="Could not parse Mastodon URL",
                metadata={"url": url},
            )
        instance = m.group(1)
        status_id = m.group(2)
        api_base = f"https://{instance}/api/v1/statuses/{status_id}"

        try:
            status_resp = await self._fetch_url(api_base, timeout=15)
            data = status_resp.json()
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url, source_platform="mastodon",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url, source_platform="mastodon",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        # Follow reblogs to the underlying status — the URL points at
        # the boost but we want to index the original content.
        if data.get("reblog"):
            data = data["reblog"]
            status_id = data.get("id", status_id)

        account = data.get("account", {}) or {}
        author = account.get("display_name") or account.get("username", "")
        acct = account.get("acct", "")
        raw_html = data.get("content", "") or ""
        text = _strip_html(raw_html)
        post_id = f"mst_{status_id}"

        # Try to fetch context (ancestors + descendants). Some instances
        # rate-limit this; non-fatal if it fails.
        ancestors: list[dict] = []
        descendants: list[dict] = []
        try:
            ctx_resp = await self._fetch_url(f"{api_base}/context", timeout=15)
            ctx = ctx_resp.json()
            ancestors = ctx.get("ancestors", []) or []
            descendants = ctx.get("descendants", []) or []
        except Exception as e:
            logger.debug("Mastodon context fetch failed for %s: %s", url, e)

        # ─── Sections ───
        sections: list[Section] = []
        order = 0

        # Ancestors first (in chronological order — Mastodon API returns
        # them oldest-first which matches reading order of a thread).
        for anc in ancestors[:10]:
            anc_id = f"mst_{anc.get('id')}"
            anc_acct = (anc.get("account") or {}).get("acct", "")
            sections.append(Section(
                id=anc_id, kind="reply", order=order,
                parent_id=None, depth=-1, role="supplemental",
                text=_strip_html(anc.get("content") or ""),
                author=anc_acct or (anc.get("account") or {}).get("display_name"),
                score=anc.get("favourites_count"),
                created_at=anc.get("created_at"),
                source_url=anc.get("url"),
                extra={"position": "ancestor"},
            ))
            order += 1

        # Main toot
        sections.append(Section(
            id=post_id, kind="post", order=order, role="main",
            text=text or "(empty toot)",
            author=acct or author,
            score=data.get("favourites_count"),
            created_at=data.get("created_at"),
            source_url=data.get("url") or url,
            extra={
                "language": data.get("language"),
                "boosts_count": data.get("reblogs_count", 0),
                "replies_count": data.get("replies_count", 0),
                "spoiler_text": data.get("spoiler_text") or None,
            },
        ))
        order += 1

        # Media alt-text → visual_caption sections (Mastodon's
        # description field is high-quality user-supplied alt text).
        for att in data.get("media_attachments", []) or []:
            alt = att.get("description")
            if alt:
                sections.append(Section(
                    id=f"mst_{status_id}_alt_{order}",
                    kind="visual_caption", order=order, parent_id=post_id,
                    role="supplemental", text=alt,
                    extra={"media_type": att.get("type"), "media_url": att.get("url")},
                ))
                order += 1

        # Descendants (responses, score-weighted)
        sorted_desc = sorted(
            descendants, key=lambda d: (d.get("favourites_count") or 0), reverse=True,
        )
        for desc in sorted_desc[:_MAX_REPLIES]:
            d_id = f"mst_{desc.get('id')}"
            d_acct = (desc.get("account") or {}).get("acct", "")
            in_reply = desc.get("in_reply_to_id")
            parent = (
                f"mst_{in_reply}" if in_reply
                and (in_reply == status_id or any(d.get("id") == in_reply for d in descendants))
                else post_id
            )
            sections.append(Section(
                id=d_id, kind="reply", order=order,
                parent_id=parent, depth=1 if parent == post_id else 2,
                role="main",
                text=_strip_html(desc.get("content") or ""),
                author=d_acct or (desc.get("account") or {}).get("display_name"),
                score=desc.get("favourites_count"),
                created_at=desc.get("created_at"),
                source_url=desc.get("url"),
            ))
            order += 1

        # Media for the cards
        media: list[dict] = []
        for att in data.get("media_attachments", []) or []:
            entry = {
                "type": att.get("type", "image"),
                "url": att.get("url", ""),
                "role": "content",
            }
            if att.get("preview_url"):
                entry["preview_url"] = att["preview_url"]
            if att.get("description"):
                entry["description"] = att["description"]
            media.append(entry)

        metadata = {
            "url": url,
            "instance": instance,
            "status_id": status_id,
            "author": acct or author,
            "acct": acct,
            "boosts_count": data.get("reblogs_count", 0),
            "favourites_count": data.get("favourites_count", 0),
            "replies_count": data.get("replies_count", 0),
            "created_at": data.get("created_at", ""),
            "language": data.get("language", ""),
            "ancestor_count": len(ancestors),
            "descendant_count_fetched": min(len(descendants), _MAX_REPLIES),
        }

        title = f"{author}: {text[:80]}..." if len(text) > 80 else f"{author}: {text}"

        return ProcessorResult(
            title=title,
            description=text[:300] if text else None,
            content=None,
            raw_content=raw_html or None,
            media=media,
            metadata=metadata,
            source_platform="mastodon",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
