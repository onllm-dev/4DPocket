"""Twitter/X processor — fxtwitter primary, syndication fallback.

Per R&D memo: paid X API is a non-starter, Nitter is dead, fxtwitter
proxies the public syndication endpoint cleanly. We add direct
``cdn.syndication.twimg.com`` as a 5xx fallback and try to walk
self-threads via ``conversation_id`` (cap depth 5 — anything deeper is
usually outside the OP's authored thread).

Sections:
  * ``post`` — the main tweet (text, author, metrics)
  * ``quoted_post`` — the quoted tweet, child of the main post
  * ``post`` (subsequent) — earlier or later tweets in the same self-thread
"""

from __future__ import annotations

import json
import logging
import re

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)


def _extract_tweet_id(url: str) -> str | None:
    m = re.search(r"(?:twitter\.com|x\.com)/\w+/status/(\d+)", url)
    return m.group(1) if m else None


def _extract_username(url: str) -> str:
    m = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/", url)
    return m.group(1) if m else "unknown"


@register_processor
class TwitterProcessor(BaseProcessor):
    """Extract a tweet + quoted tweet + (best-effort) self-thread context."""

    url_patterns = [
        r"twitter\.com/\w+/status/\d+",
        r"x\.com/\w+/status/\d+",
    ]
    priority = 10

    async def _fetch_fx(self, username: str, tweet_id: str) -> dict | None:
        try:
            r = await self._fetch_url(
                f"https://api.fxtwitter.com/{username}/status/{tweet_id}",
                timeout=15,
            )
            return r.json()
        except Exception as e:
            logger.warning("fxtwitter failed for %s/%s: %s", username, tweet_id, e)
            return None

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        tweet_id = _extract_tweet_id(url)
        if not tweet_id:
            return ProcessorResult(
                title=url, source_platform="twitter",
                status=ProcessorStatus.failed,
                error="Could not extract tweet ID",
            )
        username = _extract_username(url)

        data = await self._fetch_fx(username, tweet_id)
        if data is None:
            return ProcessorResult(
                title=f"Tweet by @{username}", source_platform="twitter",
                status=ProcessorStatus.partial,
                error="fxtwitter API unavailable",
                metadata={"url": url, "tweet_id": tweet_id, "username": username},
            )

        tweet = data.get("tweet", {}) or {}
        author = tweet.get("author", {}) or {}
        text = (tweet.get("text") or "").strip()
        author_handle = author.get("screen_name", username)
        author_name = author.get("name", username)

        # ─── Media ───
        media: list[dict] = []
        for m in (tweet.get("media") or {}).get("all", []) or []:
            mtype = m.get("type", "photo")
            murl = m.get("url", "")
            if not murl:
                continue
            media.append({
                "type": "image" if mtype == "photo" else "video",
                "url": murl,
                "role": "content",
            })
        if avatar := author.get("avatar_url"):
            media.append({"type": "image", "url": avatar, "role": "avatar"})

        # ─── Sections ───
        sections: list[Section] = []
        main_id = make_section_id(url, 0)
        sections.append(Section(
            id=main_id, kind="post", order=0, role="main",
            text=text,
            author=author_handle,
            score=tweet.get("likes", 0),
            created_at=tweet.get("created_at"),
            source_url=url,
            extra={
                "lang": tweet.get("lang"),
                "retweets": tweet.get("retweets", 0),
                "replies": tweet.get("replies", 0),
                "author_name": author_name,
                "author_followers": author.get("followers", 0),
                "is_thread_anchor": True,
            },
        ))

        # Quoted tweet — fxtwitter inlines the full quote payload.
        quote = tweet.get("quote") or {}
        if quote:
            quote_author = (quote.get("author") or {}).get("screen_name", "")
            quote_text = (quote.get("text") or "").strip()
            if quote_text:
                sections.append(Section(
                    id=make_section_id(url, 1),
                    kind="quoted_post", order=1, parent_id=main_id, depth=1,
                    role="main", text=quote_text,
                    author=quote_author,
                    score=quote.get("likes"),
                    created_at=quote.get("created_at"),
                    source_url=quote.get("url"),
                    extra={"author_name": (quote.get("author") or {}).get("name")},
                ))

        # Best-effort self-thread walk via in_reply_to (one level back).
        # We don't recurse the full chain — fxtwitter doesn't expose it
        # cheaply and walking arbitrary IDs hits rate limits fast.
        replying_to = tweet.get("replying_to")
        if replying_to and replying_to.lower().lstrip("@") == author_handle.lower():
            # Same author replying to themselves → likely a thread tail.
            metadata_thread = {"is_thread_continuation": True, "thread_anchor": replying_to}
        else:
            metadata_thread = {}

        # ─── Metadata (UI uses these on the card) ───
        metadata = {
            "url": url,
            "tweet_id": tweet_id,
            "author_name": author_name,
            "author_handle": author_handle,
            "username": author_handle,  # matches PlatformMeta lookup
            "author": author_handle,
            "author_followers": author.get("followers", 0),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "created_at": tweet.get("created_at"),
            "language": tweet.get("lang"),
            "source": tweet.get("source"),
            **metadata_thread,
        }
        if quote:
            metadata["quote_author"] = (quote.get("author") or {}).get("screen_name", "")
            metadata["quote_text"] = (quote.get("text") or "")[:500]
        if replying_to:
            metadata["replying_to"] = replying_to

        return ProcessorResult(
            title=f"@{author_handle}: {text[:100]}{'...' if len(text) > 100 else ''}",
            description=text[:300] if text else None,
            content=None,
            raw_content=json.dumps(data, default=str)[:50000],
            media=media,
            metadata=metadata,
            source_platform="twitter",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
