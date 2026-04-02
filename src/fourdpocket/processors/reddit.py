"""Reddit processor — extract posts and comments via JSON API."""

import json
import logging

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


@register_processor
class RedditProcessor(BaseProcessor):
    """Extract Reddit posts and comments by appending .json to the URL."""

    url_patterns = [
        r"reddit\.com/r/\w+/comments/",
        r"old\.reddit\.com/r/\w+/comments/",
        r"redd\.it/\w+",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        # Normalize URL
        json_url = url.rstrip("/")
        if not json_url.endswith(".json"):
            json_url += ".json"

        # Redirect redd.it short URLs
        if "redd.it/" in url:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                    resp = await client.head(url)
                    json_url = str(resp.url).rstrip("/") + ".json"
            except Exception:
                pass

        headers = {
            "User-Agent": "4DPocket/0.1 (Knowledge Base; +https://github.com/4dpocket)",
        }

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(json_url, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="reddit",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="reddit",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        # Parse the Reddit JSON structure
        # Reddit returns a list: [post_listing, comments_listing]
        if not isinstance(data, list) or len(data) < 1:
            return ProcessorResult(
                title=url,
                source_platform="reddit",
                status=ProcessorStatus.failed,
                error="Unexpected Reddit API response format",
            )

        post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})

        title = post_data.get("title", url)
        selftext = post_data.get("selftext", "")
        subreddit = post_data.get("subreddit", "")
        author = post_data.get("author", "")
        score = post_data.get("score", 0)
        num_comments = post_data.get("num_comments", 0)
        permalink = post_data.get("permalink", "")
        created_utc = post_data.get("created_utc", 0)

        # Extract top comments
        comments = []
        if len(data) > 1:
            comment_children = data[1].get("data", {}).get("children", [])
            for child in comment_children[:10]:  # top 10 comments
                if child.get("kind") != "t1":
                    continue
                comment_data = child.get("data", {})
                comments.append({
                    "author": comment_data.get("author", ""),
                    "body": comment_data.get("body", "")[:2000],
                    "score": comment_data.get("score", 0),
                })

        # Extract media
        media = []
        if post_data.get("thumbnail") and post_data["thumbnail"].startswith("http"):
            media.append({"type": "image", "url": post_data["thumbnail"], "role": "thumbnail"})

        # Check for image/video post
        if post_data.get("url") and any(
            post_data["url"].endswith(ext) for ext in (".jpg", ".png", ".gif", ".webp")
        ):
            media.append({"type": "image", "url": post_data["url"], "role": "content"})

        # Build content
        content_parts = []
        if selftext:
            content_parts.append(selftext)
        if comments:
            content_parts.append("\n\n## Top Comments\n")
            for i, comment in enumerate(comments, 1):
                content_parts.append(
                    f"**{comment['author']}** ({comment['score']} points):\n{comment['body']}\n"
                )

        metadata = {
            "url": url,
            "subreddit": subreddit,
            "author": author,
            "score": score,
            "num_comments": num_comments,
            "permalink": f"https://reddit.com{permalink}" if permalink else url,
            "created_utc": created_utc,
            "comment_count_fetched": len(comments),
        }

        # Crosspost info
        if post_data.get("crosspost_parent_list"):
            xpost = post_data["crosspost_parent_list"][0]
            metadata["crosspost_from"] = xpost.get("subreddit_name_prefixed", "")

        return ProcessorResult(
            title=f"[r/{subreddit}] {title}" if subreddit else title,
            description=selftext[:300] if selftext else None,
            content="\n\n".join(content_parts) if content_parts else None,
            raw_content=json.dumps(post_data, default=str)[:100000],
            media=media,
            metadata=metadata,
            source_platform="reddit",
            item_type="url",
            status=ProcessorStatus.success,
        )
