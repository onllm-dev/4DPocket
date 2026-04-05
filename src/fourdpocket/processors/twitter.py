"""Twitter/X processor - extract tweets via fxtwitter API."""

import json
import logging
import re

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


def _extract_tweet_id(url: str) -> str | None:
    """Extract tweet ID from Twitter/X URL."""
    match = re.search(r"(?:twitter\.com|x\.com)/\w+/status/(\d+)", url)
    return match.group(1) if match else None


@register_processor
class TwitterProcessor(BaseProcessor):
    """Extract tweet content via fxtwitter.com API."""

    url_patterns = [
        r"twitter\.com/\w+/status/\d+",
        r"x\.com/\w+/status/\d+",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        tweet_id = _extract_tweet_id(url)
        if not tweet_id:
            return ProcessorResult(
                title=url,
                source_platform="twitter",
                status=ProcessorStatus.failed,
                error="Could not extract tweet ID",
            )

        # Extract username from URL
        username_match = re.search(r"(?:twitter\.com|x\.com)/(\w+)/status/", url)
        username = username_match.group(1) if username_match else "unknown"

        # Try fxtwitter API
        fx_url = f"https://api.fxtwitter.com/{username}/status/{tweet_id}"

        try:
            response = await self._fetch_url(fx_url, timeout=15)
            data = response.json()
        except Exception as e:
            logger.warning("fxtwitter API failed for %s: %s", url, e)
            # Fall back to URL-only result
            return ProcessorResult(
                title=f"Tweet by @{username}",
                source_platform="twitter",
                status=ProcessorStatus.partial,
                error=f"Could not fetch tweet: {str(e)[:200]}",
                metadata={"url": url, "tweet_id": tweet_id, "username": username},
            )

        tweet = data.get("tweet", {})
        author = tweet.get("author", {})
        text = tweet.get("text", "")
        author_name = author.get("name", username)
        author_handle = author.get("screen_name", username)

        # Extract media
        media = []
        for m in tweet.get("media", {}).get("all", []):
            media_type = m.get("type", "photo")
            media_url = m.get("url", "")
            if media_url:
                media.append({
                    "type": "image" if media_type == "photo" else "video",
                    "url": media_url,
                    "role": "content",
                })

        # Author avatar
        avatar = author.get("avatar_url", "")
        if avatar:
            media.append({"type": "image", "url": avatar, "role": "avatar"})

        metadata = {
            "url": url,
            "tweet_id": tweet_id,
            "author_name": author_name,
            "author_handle": author_handle,
            "author_followers": author.get("followers", 0),
            "likes": tweet.get("likes", 0),
            "retweets": tweet.get("retweets", 0),
            "replies": tweet.get("replies", 0),
            "created_at": tweet.get("created_at"),
            "language": tweet.get("lang"),
            "source": tweet.get("source"),
        }

        # Check for thread/quote
        if tweet.get("quote"):
            quote = tweet["quote"]
            metadata["quote_text"] = quote.get("text", "")[:500]
            metadata["quote_author"] = quote.get("author", {}).get("screen_name", "")

        if tweet.get("replying_to"):
            metadata["replying_to"] = tweet["replying_to"]

        return ProcessorResult(
            title=f"@{author_handle}: {text[:100]}{'...' if len(text) > 100 else ''}",
            description=text[:300] if text else None,
            content=text,
            raw_content=json.dumps(data, default=str)[:50000],
            media=media,
            metadata=metadata,
            source_platform="twitter",
            item_type="url",
            status=ProcessorStatus.success,
        )
