"""Hacker News processor — extract items via Algolia API."""

import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


def _extract_item_id(url: str) -> str | None:
    match = re.search(r"[?&]id=(\d+)", url)
    return match.group(1) if match else None


def _collect_comments(children: list, limit: int = 10) -> list[dict]:
    comments = []
    for child in children:
        if len(comments) >= limit:
            break
        if child.get("type") == "comment" and child.get("text"):
            comments.append({
                "author": child.get("author", ""),
                "text": child.get("text", "")[:2000],
                "points": child.get("points", 0),
            })
        if child.get("children") and len(comments) < limit:
            comments.extend(_collect_comments(child["children"], limit - len(comments)))
    return comments


@register_processor
class HackerNewsProcessor(BaseProcessor):
    """Extract HN items (stories, comments) via the Algolia API."""

    url_patterns = [r"news\.ycombinator\.com/item"]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        item_id = _extract_item_id(url)
        if not item_id:
            return ProcessorResult(
                title=url,
                source_platform="hackernews",
                status=ProcessorStatus.failed,
                error="Could not extract item ID from URL",
                metadata={"url": url},
            )

        api_url = f"https://hn.algolia.com/api/v1/items/{item_id}"
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="hackernews",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url, "item_id": item_id},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="hackernews",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        title = data.get("title") or url
        author = data.get("author", "")
        score = data.get("points", 0)
        text = data.get("text", "")
        children = data.get("children", [])

        top_comments = _collect_comments(children, limit=10)

        content_parts = []
        if text:
            content_parts.append(text)
        if top_comments:
            content_parts.append("\n\n## Top Comments\n")
            for comment in top_comments:
                content_parts.append(
                    f"**{comment['author']}**:\n{comment['text']}\n"
                )

        metadata = {
            "url": url,
            "item_id": item_id,
            "author": author,
            "score": score,
            "comment_count_fetched": len(top_comments),
        }

        return ProcessorResult(
            title=title,
            description=text[:300] if text else None,
            content="\n\n".join(content_parts) if content_parts else None,
            metadata=metadata,
            source_platform="hackernews",
            item_type="url",
            status=ProcessorStatus.success,
        )
