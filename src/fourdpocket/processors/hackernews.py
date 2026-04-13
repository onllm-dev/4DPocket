"""Hacker News processor — story + threaded comments via Algolia API.

Per R&D memo: Algolia returns the entire tree (story + every comment with
body) in one call, which is what we want. Firebase API would need N+1
recursive calls. We walk the tree depth-first, score-weighted, and cap at
~80 comments / depth 6 to keep embedding costs sane.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section

logger = logging.getLogger(__name__)

_MAX_COMMENTS = 80
_MAX_DEPTH = 6


def _extract_item_id(url: str) -> str | None:
    m = re.search(r"[?&]id=(\d+)", url)
    return m.group(1) if m else None


def _walk(children: list, parent_id: str, depth: int, bucket: list[tuple[dict, str, int]]) -> None:
    if depth > _MAX_DEPTH or len(bucket) >= _MAX_COMMENTS:
        return
    sorted_children = sorted(
        (c for c in (children or []) if c.get("type") == "comment"),
        key=lambda c: c.get("points", 0) or 0,
        reverse=True,
    )
    for c in sorted_children:
        if len(bucket) >= _MAX_COMMENTS:
            return
        text = (c.get("text") or "").strip()
        if not text:
            continue
        cid = f"hnc_{c.get('id')}"
        bucket.append((c, parent_id, depth))
        _walk(c.get("children") or [], cid, depth + 1, bucket)


@register_processor
class HackerNewsProcessor(BaseProcessor):
    """HN story with full comment tree as sections."""

    url_patterns = [r"news\.ycombinator\.com/item"]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        item_id = _extract_item_id(url)
        if not item_id:
            return ProcessorResult(
                title=url, source_platform="hackernews",
                status=ProcessorStatus.failed,
                error="Could not extract item ID from URL",
                metadata={"url": url},
            )

        api_url = f"https://hn.algolia.com/api/v1/items/{item_id}"
        try:
            r = await self._fetch_url(api_url, timeout=15)
            data = r.json()
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url, source_platform="hackernews",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url, "item_id": item_id},
            )
        except Exception as e:
            return ProcessorResult(
                title=url, source_platform="hackernews",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        title = data.get("title") or url
        author = data.get("author") or ""
        score = data.get("points") or 0
        text = (data.get("text") or "").strip()
        children = data.get("children") or []
        story_url_field = data.get("url")

        story_id = f"hns_{data.get('id', item_id)}"
        sections: list[Section] = []

        # Story body — title + selftext for Ask/Show HN, or just title
        # for link submissions (where the URL is the content).
        story_text = title if not text else f"{title}\n\n{text}"
        sections.append(Section(
            id=story_id, kind="post", order=0, role="main",
            text=story_text,
            author=author, score=score,
            created_at=data.get("created_at"),
            source_url=url,
            extra={
                "story_url": story_url_field,
                "kind": "ask" if data.get("title", "").startswith("Ask HN:") else None,
            },
        ))

        bucket: list[tuple[dict, str, int]] = []
        _walk(children, story_id, 1, bucket)
        for i, (c, parent_id, depth) in enumerate(bucket, 1):
            kind = "reply" if depth > 1 else "comment"
            sections.append(Section(
                id=f"hnc_{c.get('id')}",
                kind=kind, order=i, parent_id=parent_id, depth=depth,
                role="main",
                text=(c.get("text") or "").strip(),
                author=c.get("author"),
                score=c.get("points"),
                created_at=c.get("created_at"),
                source_url=f"https://news.ycombinator.com/item?id={c.get('id')}",
            ))

        metadata = {
            "url": url,
            "item_id": item_id,
            "author": author,
            "score": score,
            "comment_count_fetched": len(bucket),
            "story_url": story_url_field,
        }

        return ProcessorResult(
            title=title,
            description=text[:300] if text else None,
            content=None,
            raw_content=json.dumps(data, default=str)[:100000],
            metadata=metadata,
            source_platform="hackernews",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
