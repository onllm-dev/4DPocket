"""Reddit processor — post + threaded comments via the public .json endpoint.

Per R&D memo (Phase 2 platform strategy): we use Reddit's own ``.json``
endpoint, not PRAW. It returns the same data as the OAuth API, requires
no auth, and is one HTTP call. Reddit blocks ``python-requests/*`` and
similar UAs, so we send a project-branded one and add ``raw_json=1`` so
we don't have to hand-unescape ``&amp;`` later.

Sections:
  * one ``post`` section for the OP (selftext, score, author, subreddit)
  * recursive ``comment``/``reply`` sections with parent_id + depth +
    score + author. Top-N selection is score-weighted depth-first so a
    well-scored deep thread isn't dropped in favor of a stub top-level.
"""

from __future__ import annotations

import json
import logging
from html import unescape

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section

logger = logging.getLogger(__name__)

# Reddit explicitly rejects generic library UAs. A descriptive UA is
# also their stated etiquette in the API rules. Bumping the version is
# fine — the string just has to be reasonable.
_REDDIT_USER_AGENT = "4dpocket/0.2 (knowledge-base ingester; +https://github.com/4dpocket)"

# Cap how many comments we keep per post. Big threads (e.g. AskReddit
# popular posts) can return thousands; keeping all of them blows up
# embedding cost and rarely improves recall.
_MAX_COMMENTS = 80
_MAX_COMMENT_DEPTH = 5


def _walk_comments(
    children: list,
    parent_id: str,
    depth: int,
    bucket: list[tuple[dict, str, int]],
) -> None:
    """Score-weighted depth-first flatten of the comment tree.

    Appends ``(comment_data, parent_id, depth)`` tuples to ``bucket``. We
    stop descending past ``_MAX_COMMENT_DEPTH`` and skip ``kind=more``
    continuation tokens (we don't issue follow-up calls — a separate
    enrichment pass could add that later if users ask for it).
    """
    if depth > _MAX_COMMENT_DEPTH or len(bucket) >= _MAX_COMMENTS:
        return
    # Sort siblings by score so well-rated branches come first.
    sorted_children = sorted(
        (c for c in children if c.get("kind") == "t1"),
        key=lambda c: c.get("data", {}).get("score", 0),
        reverse=True,
    )
    for child in sorted_children:
        if len(bucket) >= _MAX_COMMENTS:
            return
        cdata = child.get("data", {})
        body = (cdata.get("body") or "").strip()
        if not body or body in ("[deleted]", "[removed]"):
            continue
        bucket.append((cdata, parent_id, depth))
        replies = cdata.get("replies")
        if isinstance(replies, dict):
            sub_children = replies.get("data", {}).get("children", [])
            _walk_comments(sub_children, parent_id_for(cdata), depth + 1, bucket)


def parent_id_for(cdata: dict) -> str:
    """Stable id for a Reddit comment so children can reference it."""
    return f"rdc_{cdata.get('id') or cdata.get('name') or ''}"


@register_processor
class RedditProcessor(BaseProcessor):
    """Extract a Reddit submission with threaded comments as sections."""

    url_patterns = [
        r"reddit\.com/r/\w+/comments/",
        r"old\.reddit\.com/r/\w+/comments/",
        r"redd\.it/\w+",
    ]
    priority = 10

    async def _fetch_reddit_json(self, url: str) -> tuple[list, str]:
        """Fetch the json endpoint with a Reddit-friendly UA. Returns (data, final_url)."""
        json_url = url.rstrip("/")
        if not json_url.endswith(".json"):
            json_url += ".json"
        # Force public sort + threaded view; raw_json skips HTML entity escaping
        sep = "&" if "?" in json_url else "?"
        json_url = f"{json_url}{sep}raw_json=1&sort=top&threaded=true&limit=500"

        headers = {
            "User-Agent": _REDDIT_USER_AGENT,
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(json_url, headers=headers)
            r.raise_for_status()
        return r.json(), str(r.url)

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        # redd.it shorteners → resolve via plain GET first
        if "redd.it/" in url:
            try:
                resp = await self._fetch_url(url, timeout=15)
                url = str(resp.url)
            except Exception:
                pass

        try:
            data, _final = await self._fetch_reddit_json(url)
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

        if not isinstance(data, list) or len(data) < 1:
            return ProcessorResult(
                title=url,
                source_platform="reddit",
                status=ProcessorStatus.failed,
                error="Unexpected Reddit API response format",
            )

        post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})

        title = post_data.get("title") or url
        selftext = (post_data.get("selftext") or "").strip()
        subreddit = post_data.get("subreddit", "")
        author = post_data.get("author", "")
        score = post_data.get("score", 0)
        num_comments = post_data.get("num_comments", 0)
        permalink = post_data.get("permalink", "")
        created_utc = post_data.get("created_utc", 0)
        flair = post_data.get("link_flair_text") or None
        is_self = bool(post_data.get("is_self"))

        post_id = f"rdp_{post_data.get('id', '0')}"

        # ─── Sections ───
        sections: list[Section] = []
        sections.append(Section(
            id=post_id,
            kind="post",
            order=0,
            role="main",
            text=f"{title}\n\n{selftext}".strip() if selftext else title,
            author=author,
            score=score,
            created_at=str(created_utc) if created_utc else None,
            source_url=f"https://reddit.com{permalink}" if permalink else url,
            extra={
                "subreddit": subreddit,
                "flair": flair,
                "is_self": is_self,
                "num_comments": num_comments,
            },
        ))

        comment_rows: list[tuple[dict, str, int]] = []
        if len(data) > 1:
            children = data[1].get("data", {}).get("children", [])
            _walk_comments(children, post_id, 1, comment_rows)

        for i, (cdata, parent_id, depth) in enumerate(comment_rows, start=1):
            kind = "reply" if depth > 1 else "comment"
            sections.append(Section(
                id=parent_id_for(cdata),
                kind=kind,
                order=i,
                parent_id=parent_id,
                depth=depth,
                role="main",
                text=(cdata.get("body") or "").strip(),
                author=cdata.get("author"),
                score=cdata.get("score"),
                created_at=str(cdata.get("created_utc")) if cdata.get("created_utc") else None,
                source_url=(
                    f"https://reddit.com{cdata.get('permalink')}"
                    if cdata.get("permalink") else None
                ),
                is_accepted=False,
                extra={"is_submitter": cdata.get("is_submitter", False)},
            ))

        # ─── Media ───
        media: list[dict] = []
        thumb = post_data.get("thumbnail")
        if isinstance(thumb, str) and thumb.startswith("http"):
            # Reddit thumbnails are often i.redd.it preview URLs that need
            # a User-Agent + cookie to load — the fetcher's media-proxy
            # endpoint already handles that for licdn/preview.redd.it.
            media.append({"type": "image", "url": unescape(thumb), "role": "thumbnail"})
        # Image submissions: the post URL itself is the media
        post_url = unescape(post_data.get("url", ""))
        if post_url:
            ext = post_url.rsplit("?", 1)[0].lower()
            if any(ext.endswith(e) for e in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
                media.append({"type": "image", "url": post_url, "role": "content"})
            elif post_data.get("is_video") or "v.redd.it" in post_url:
                media.append({
                    "type": "video",
                    "url": post_url,
                    "role": "content",
                })
            elif "youtube.com" in post_url or "youtu.be" in post_url:
                # Linked youtube post — keep as media reference; user can
                # follow the link.
                media.append({"type": "video", "url": post_url, "role": "external"})

        # ─── Metadata (back-compat fields the UI already reads) ───
        metadata = {
            "url": url,
            "subreddit": subreddit,
            "author": author,
            "score": score,
            "num_comments": num_comments,
            "permalink": f"https://reddit.com{permalink}" if permalink else url,
            "created_utc": created_utc,
            "comment_count_fetched": len(comment_rows),
            "comment_count_total": num_comments,
        }
        if flair:
            metadata["flair"] = flair
        if post_data.get("crosspost_parent_list"):
            xpost = post_data["crosspost_parent_list"][0]
            metadata["crosspost_from"] = xpost.get("subreddit_name_prefixed", "")

        return ProcessorResult(
            title=f"[r/{subreddit}] {title}" if subreddit else title,
            description=selftext[:300] if selftext else None,
            # Sections drive content in the fetcher; keep a flat fallback
            # for callers that bypass the fetcher.
            content=None,
            raw_content=json.dumps(post_data, default=str)[:100000],
            media=media,
            metadata=metadata,
            source_platform="reddit",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
