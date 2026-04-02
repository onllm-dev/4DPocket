"""Mastodon processor - extract posts via ActivityPub instance API."""

import logging
import re
from html.parser import HTMLParser

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


class _HTMLStripper(HTMLParser):
    """Minimal HTML-to-text stripper."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


@register_processor
class MastodonProcessor(BaseProcessor):
    """Extract Mastodon statuses via the instance's v1 API."""

    url_patterns = [
        r"/@[^/]+/\d+",
    ]
    priority = 8

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        try:
            # Extract instance hostname and status ID from URL
            match = re.search(r"https?://([^/]+)/@[^/]+/(\d+)", url)
            if not match:
                return ProcessorResult(
                    title=url,
                    source_platform="mastodon",
                    status=ProcessorStatus.failed,
                    error="Could not parse Mastodon URL",
                    metadata={"url": url},
                )

            instance = match.group(1)
            status_id = match.group(2)
            api_url = f"https://{instance}/api/v1/statuses/{status_id}"

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(api_url)
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="mastodon",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="mastodon",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        account = data.get("account", {})
        author = account.get("display_name") or account.get("username", "")
        acct = account.get("acct", "")

        raw_html = data.get("content", "")
        content = _strip_html(raw_html)

        # Media attachments
        media = []
        for attachment in data.get("media_attachments", []):
            media.append({
                "type": attachment.get("type", "image"),
                "url": attachment.get("url", ""),
                "preview_url": attachment.get("preview_url", ""),
                "description": attachment.get("description", ""),
            })

        metadata = {
            "url": url,
            "instance": instance,
            "status_id": status_id,
            "author": author,
            "acct": acct,
            "boosts_count": data.get("reblogs_count", 0),
            "favourites_count": data.get("favourites_count", 0),
            "replies_count": data.get("replies_count", 0),
            "created_at": data.get("created_at", ""),
            "language": data.get("language", ""),
        }

        title = f"{author}: {content[:80]}..." if len(content) > 80 else f"{author}: {content}"

        return ProcessorResult(
            title=title,
            description=content[:300] if content else None,
            content=content or None,
            raw_content=raw_html or None,
            media=media,
            metadata=metadata,
            source_platform="mastodon",
            item_type="url",
            status=ProcessorStatus.success,
        )
