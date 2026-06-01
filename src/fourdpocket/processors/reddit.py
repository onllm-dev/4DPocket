"""Reddit processor — post + threaded comments scraped from old.reddit.com HTML.

Per R&D memo: Reddit now blocks unauthenticated .json requests with 403.
Plain httpx + Chrome UA successfully fetches HTML from old.reddit.com.

Sections:
  * one ``post`` section for the OP (selftext, score, author, subreddit)
  * recursive ``comment``/``reply`` sections with parent_id + depth +
    score + author. Top-N selection is score-weighted depth-first so a
    well-scored deep thread isn't dropped in favor of a stub top-level.
"""

from __future__ import annotations

import asyncio
import logging
import re
from html import unescape
from urllib.parse import urlsplit, urlunsplit

import httpx
from lxml import html as lxml_html

from fourdpocket.processors.base import (
    BaseProcessor,
    ProcessorResult,
    ProcessorStatus,
    _is_safe_url,
)
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section

logger = logging.getLogger(__name__)

_REDDIT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_MAX_COMMENTS = 80
_MAX_COMMENT_DEPTH = 5

# Reddit 403s intermittently even from allow-listed IPs; retry the HTML fetch.
_FETCH_RETRIES = 4
_RETRY_DELAY = 2.0


def _old_reddit_url(url: str) -> str:
    """Convert any reddit.com URL to old.reddit.com, dropping query + fragment.

    Share links carry ``?share_id=...&utm_...`` query strings; leaving them in
    place mangled the URL once a trailing slash was appended for the HTML fetch.
    """
    parts = urlsplit(url)
    netloc = re.sub(r"^(?:www\.|m\.)?reddit\.com$", "old.reddit.com", parts.netloc)
    return urlunsplit((parts.scheme, netloc, parts.path.rstrip("/"), "", ""))


def _strip_html(html_str: str | None) -> str:
    """Strip HTML tags, decode entities, collapse whitespace."""
    if not html_str:
        return ""
    try:
        doc = lxml_html.fromstring(html_str)
        text = doc.text_content() or ""
    except Exception:
        text = re.sub(r"<[^>]+>", "", html_str)
    return re.sub(r"\s+", " ", text).strip()


def _strip_type_prefix(id_str: str) -> str:
    """Strip t1_, t3_, rdp_, rdc_ type prefixes to get the raw ID."""
    for prefix in ("t1_", "t3_", "rdp_", "rdc_"):
        if id_str.startswith(prefix):
            return id_str[len(prefix):]
    return id_str


def _walk_html_comments(
    root,
    post_id: str,
    max_depth: int,
    bucket: list,
) -> None:
    """Score-weighted depth-first flatten of the comment tree from HTML.

    Works with both the live ``div.thing`` format (data-* on thing) and the
    fixture ``div.entry`` format (data-* on entry div).

    Appends (thing_element, parent_id, depth) to bucket. Stops at max_depth
    and when bucket reaches _MAX_COMMENTS.
    """
    if len(bucket) >= _MAX_COMMENTS:
        return
    if root is None:
        return

    post_raw_id = _strip_type_prefix(post_id)

    # Find entry elements — works for both formats:
    # live:    div.thing > div.entry (data-* on thing, entry is child)
    # fixture: div.entry             (data-* on entry div itself)
    all_entries = root.xpath('//div[contains(@class,"entry")]')
    if not all_entries:
        return

    # Determine format by checking if entries have data-fullname directly
    # (fixture) or if their parent thing does (live)
    first_entry = all_entries[0]
    first_thing = first_entry.getparent()  # type: ignore[attr-defined]
    is_live_format = (
        first_thing is not None
        and first_thing.get("data-score") is not None
    )

    if is_live_format:
        # Convert entry elements to their parent thing elements
        thing_by_id: dict[str, object] = {}
        for thing in root.xpath('//div[contains(@class,"thing")]'):
            fn = thing.get("data-fullname", "")
            if fn:
                thing_by_id[fn] = thing
        _walk_live_format(root, thing_by_id, post_raw_id, max_depth, bucket)
    else:
        _walk_fixture_format(all_entries, post_raw_id, max_depth, bucket)


def _walk_live_format(
    root,
    thing_by_id: dict[str, object],
    post_raw_id: str,
    max_depth: int,
    bucket: list,
) -> None:
    """Handle live old.reddit.com HTML: div.thing with data-* on thing.

    Nesting is determined by DOM position, NOT by p.parent.anchor matching.
    In old.reddit HTML, every comment has a self-referential anchor; the
    actual parent-child relationship is encoded in the DOM hierarchy:

        div.thing (parent comment, data-type=comment)
          div.entry
          div.child                      ← sibling of entry inside the thing
            div.sitetable.listing
              div.thing (child comment) ← nested here

    So a comment's true parent is found by walking UP:
      thing.getparent() -> sitetable.listing
      sitetable.getparent() -> div.child
      div.child.getparent() -> parent comment div.thing
    """

    by_id: dict[str, object] = thing_by_id

    def _score(thing) -> int:
        val = thing.get("data-score", "")
        if val and val.lstrip("-").isdigit():
            return int(val)
        return 0

    def _body(thing) -> str:
        bodies = thing.xpath('.//div[contains(@class,"usertext-body")]')
        if bodies:
            return _strip_html(bodies[0].text_content() or "")
        return ""

    def _get_children(comment_fn: str) -> list[tuple[str, object]]:
        """Get child comment things for a given parent comment fullname."""
        parent_thing = by_id.get(comment_fn)
        if parent_thing is None:
            return []
        # Find div.child sibling inside parent_thing
        child_div = None
        for sib in parent_thing:
            if "child" in sib.get("class", ""):
                child_div = sib
                break
        if child_div is None:
            return []
        st_list = child_div.xpath('./div[contains(@class,"sitetable")]')
        if not st_list:
            return []
        st = st_list[0]
        children = []
        for child_thing in st:
            cfn = child_thing.get("data-fullname", "")
            if cfn and cfn.startswith("t1_"):
                children.append((cfn, child_thing))
        return children

    seen_ids: set[str] = set()

    # Top-level comments: in a sitetable.nestedlisting
    nestedlisting = None
    for nl in root.xpath('//div[contains(@class,"nestedlisting")]'):
        nl_parent = nl.getparent()
        if nl_parent is not None and "commentarea" in nl_parent.get("class", ""):
            nestedlisting = nl
            break

    def _walk_node(comment_fn: str, depth: int, already_seen: bool) -> None:
        """Recursively walk children of a comment.

        already_seen is True when this comment was already added to the bucket
        as a top-level comment (so we skip re-adding but still walk children).
        """
        if depth > max_depth or len(bucket) >= _MAX_COMMENTS:
            return
        if already_seen:
            # Already in bucket; only walk children, don't add again
            children = _get_children(comment_fn)
            if not children:
                return
            children.sort(key=lambda x: _score(x[1]), reverse=True)
            for cfn, child_thing in children:
                if cfn in seen_ids:
                    continue
                body = _body(child_thing)
                if not body or body in ("[deleted]", "[removed]"):
                    continue
                # Add child and recurse
                seen_ids.add(cfn)
                bucket.append((child_thing, f"rdc_{comment_fn[3:]}", depth))
                _walk_node(cfn, depth + 1, False)
            return
        if comment_fn in seen_ids:
            return

        children = _get_children(comment_fn)
        if not children:
            return
        children.sort(key=lambda x: _score(x[1]), reverse=True)
        for cfn, child_thing in children:
            body = _body(child_thing)
            if not body or body in ("[deleted]", "[removed]"):
                continue
            if cfn in seen_ids:
                continue
            seen_ids.add(cfn)
            bucket.append((child_thing, f"rdc_{comment_fn[3:]}", depth))
            _walk_node(cfn, depth + 1, False)

    # Top-level: add to bucket first, then recurse into children
    if nestedlisting is not None:
        top_level_candidates = []
        for thing in nestedlisting.xpath('./div[contains(@class,"thing")]'):
            if thing.get("data-type") != "comment":
                continue
            fn = thing.get("data-fullname", "")
            if not fn:
                continue
            body = _body(thing)
            if not body or body in ("[deleted]", "[removed]"):
                continue
            top_level_candidates.append((fn, thing, _score(thing)))

        top_level_candidates.sort(key=lambda x: x[2], reverse=True)
        for fn, thing, _ in top_level_candidates:
            if len(bucket) >= _MAX_COMMENTS:
                break
            if fn in seen_ids:
                continue
            seen_ids.add(fn)
            bucket.append((thing, f"rdp_{post_raw_id}", 1))
            _walk_node(fn, 2, True)  # True: already added to bucket


def _walk_fixture_format(
    all_things: list,
    post_raw_id: str,
    max_depth: int,
    bucket: list,
) -> None:
    """Handle fixture HTML: div.entry with data-* on entry div.

    In the fixture format, entries are inside div.sitetable and replies
    are nested inside their parent's div.entry for rendering.
    """
    # Filter to entries (not nested reply entries)
    entries = [
        e for e in all_things
        if _strip_type_prefix(e.get("data-fullname", "")) != post_raw_id
    ]

    # Group by parent
    by_parent: dict[str, list] = {}
    for entry in entries:
        parent_raw = entry.get("data-parent", "")
        pid = _strip_type_prefix(parent_raw) if parent_raw else post_raw_id
        if pid not in by_parent:
            by_parent[pid] = []
        by_parent[pid].append(entry)

    def _score(el) -> int:
        score_span = el.find('.//span[@class="score"]')
        if score_span is not None:
            val = score_span.get("data-score", "")
            if val and val.lstrip("-").isdigit():
                return int(val)
        return 0

    def _body(el) -> str:
        ut = el.find('./div[@class="usertext-body"]')
        if ut is not None:
            return _strip_html(ut.text_content() or "")
        return ""

    def _comment_id(el) -> str:
        return el.get("data-fullname", "")

    visited: set[tuple[str, int]] = set()
    seen_ids: set[str] = set()

    def _walk_node(parent_key: str, depth: int) -> None:
        if depth > max_depth or len(bucket) >= _MAX_COMMENTS:
            return
        key = (parent_key, depth)
        if key in visited:
            return
        visited.add(key)

        children = by_parent.get(parent_key, [])
        sorted_children = sorted(children, key=_score, reverse=True)
        for child in sorted_children:
            if len(bucket) >= _MAX_COMMENTS:
                return
            cid = _comment_id(child)
            body = _body(child)
            if cid and cid in seen_ids:
                continue
            if not body or body in ("[deleted]", "[removed]"):
                continue
            if cid:
                seen_ids.add(cid)
            if parent_key == post_raw_id:
                parent_id = f"rdp_{post_raw_id}"
            else:
                parent_id = f"rdc_{parent_key}"
            bucket.append((child, parent_id, depth))
            if cid:
                _walk_node(_strip_type_prefix(cid), depth + 1)

    _walk_node(post_raw_id, 1)


@register_processor
class RedditProcessor(BaseProcessor):
    """Extract a Reddit submission with threaded comments as sections."""

    url_patterns = [
        r"reddit\.com/r/[\w-]+/comments/",
        r"old\.reddit\.com/r/[\w-]+/comments/",
        r"reddit\.com/r/[\w-]+/s/\w+",
        r"redd\.it/\w+",
    ]
    priority = 10

    async def _fetch_old_reddit_html(self, url: str) -> tuple[str, str]:
        """Fetch old.reddit.com HTML. Returns (html, final_url)."""
        html_url = _old_reddit_url(url)
        if not html_url.endswith("/"):
            html_url += "/"

        headers = {
            "User-Agent": _REDDIT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        if not _is_safe_url(html_url):
            raise ValueError("URL blocked: targets internal network")
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for attempt in range(_FETCH_RETRIES):
                r = await client.get(html_url, headers=headers)
                if r.status_code == 403 and attempt < _FETCH_RETRIES - 1:
                    await asyncio.sleep(_RETRY_DELAY * (attempt + 1))
                    continue
                break
            r.raise_for_status()
        return r.text, str(r.url)

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        # redd.it shorteners and /s/ share links → resolve to the canonical
        # /comments/ URL via a plain GET first. old.reddit.com 403s on /s/
        # paths, so the redirect must be followed on www.reddit.com.
        if "redd.it/" in url or re.search(r"/r/[\w-]+/s/\w+", url):
            try:
                resp = await self._fetch_url(url, timeout=15)
                url = str(resp.url)
            except Exception:
                pass

        try:
            raw_html, final_url = await self._fetch_old_reddit_html(url)
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

        try:
            doc = lxml_html.fromstring(raw_html)
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="reddit",
                status=ProcessorStatus.failed,
                error=f"HTML parse error: {e}",
                metadata={"url": url},
            )

        # ─── Post extraction ───────────────────────────────────────────────
        title_text = ""
        title_el = doc.xpath("//title/text()")
        if title_el:
            raw_title = title_el[0].strip()
            if " : " in raw_title:
                title_text = raw_title.split(" : ", 1)[0].strip()
            else:
                title_text = raw_title

        # Post ID from URL
        post_id_match = re.search(r"/comments/([\w-]+)/", final_url)
        post_id = f"rdp_{post_id_match.group(1)}" if post_id_match else "rdp_0"

        # Try live format first: div.thing with data-*
        post_thing = None
        all_things = doc.xpath('//div[contains(@class,"thing")]')
        for t in all_things:
            if t.get("data-type") == "link":
                post_thing = t
                break

        if post_thing is not None:
            # Live format extraction
            author = post_thing.get("data-author", "") or ""
            subreddit = post_thing.get("data-subreddit", "") or ""
            score = 0
            val = post_thing.get("data-score", "")
            if val and val.lstrip("-").isdigit():
                score = int(val)
            num_comments = 0
            nc = post_thing.get("data-comments-count", "")
            if nc and nc.isdigit():
                num_comments = int(nc)
            flair = None
            flair_el = post_thing.xpath('.//span[contains(@class,"linkflairtext")]')
            if flair_el:
                flair = flair_el[0].text_content().strip() or None
            selftext = ""
            ut = post_thing.xpath('.//div[contains(@class,"usertext-body")]')
            if ut:
                selftext = _strip_html(ut[0].text_content() or "")
            permalink = post_thing.get("data-permalink", "") or ""
            created_utc = None
            ts = post_thing.get("data-timestamp", "")
            if ts and ts.isdigit():
                created_utc = str(int(int(ts) / 1000))
            is_self = bool(selftext)
            source_url = f"https://reddit.com{permalink}" if permalink else final_url
        else:
            # Fixture format fallback
            author = ""
            author_el = doc.xpath('//a[@class="author"]')
            if author_el:
                author = author_el[0].text_content().strip()
            subreddit = ""
            sub_el = doc.xpath('//a[@class="subreddit"]')
            if sub_el:
                subreddit = sub_el[0].text_content().strip()
                if subreddit.startswith("r/"):
                    subreddit = subreddit[2:]
            score = 0
            score_el = doc.xpath('//div[contains(@class,"entry")]//span[@class="score"]')
            if score_el:
                val = score_el[0].get("data-score", "0")
                if val.lstrip("-").isdigit():
                    score = int(val)
            num_comments = 0
            comments_el = doc.xpath('//a[@class="comments"]')
            if comments_el:
                nc = comments_el[0].get("data-num-comments", "0")
                if nc.isdigit():
                    num_comments = int(nc)
            flair = None
            flair_el = doc.xpath('//span[contains(@class,"linkflairtext")]')
            if flair_el:
                flair = flair_el[0].text_content().strip() or None
            selftext = ""
            post_entries = doc.xpath(
                '//div[contains(@class,"entry")][starts-with(@data-fullname,"t3_")]/div[@class="usertext-body"]'
            )
            if post_entries:
                selftext = _strip_html(post_entries[0].text_content() or "")
            permalink = ""
            permalink_el = doc.xpath('//link[@rel="canonical"]')
            if permalink_el:
                permalink = permalink_el[0].get("href", "")
            created_utc = None
            time_el = doc.xpath('//time[@datetime]')
            if time_el:
                dt = time_el[0].get("datetime", "")
                try:
                    from datetime import datetime
                    dt_obj = datetime.fromisoformat(dt.replace("Z", "+00:00"))
                    created_utc = str(int(dt_obj.timestamp()))
                except Exception:
                    pass
            is_self = bool(selftext)
            source_url = f"https://reddit.com{permalink}" if permalink else final_url

        # ─── Sections ───────────────────────────────────────────────────────
        sections: list[Section] = []
        sections.append(Section(
            id=post_id,
            kind="post",
            order=0,
            role="main",
            text=f"{title_text}\n\n{selftext}".strip() if selftext else title_text,
            author=author,
            score=score,
            created_at=created_utc,
            source_url=source_url,
            extra={
                "subreddit": subreddit,
                "flair": flair,
                "is_self": is_self,
                "num_comments": num_comments,
            },
        ))

        # ─── Comments ───────────────────────────────────────────────────────
        comment_bucket: list = []
        _walk_html_comments(doc, post_id, _MAX_COMMENT_DEPTH, comment_bucket)

        def _make_section_id(thing_el) -> str:
            fid = thing_el.get("data-fullname", "")
            raw = _strip_type_prefix(fid) if fid else f"sec_{len(sections)}"
            return f"rdc_{raw}" if not raw.startswith("rdc_") else raw

        for i, (cel, parent_id, depth) in enumerate(comment_bucket, start=1):
            kind = "reply" if depth > 1 else "comment"
            sections.append(Section(
                id=_make_section_id(cel),
                kind=kind,
                order=i,
                parent_id=parent_id,
                depth=depth,
                role="main",
                text=_cel_body(cel),
                author=_cel_author(cel),
                score=_cel_score(cel),
                created_at=_cel_created(cel),
                source_url=_cel_permalink(cel),
                is_accepted=False,
                extra={"is_submitter": _cel_is_submitter(cel)},
            ))

        # ─── Media ─────────────────────────────────────────────────────────
        media: list[dict] = []
        thumb_els = doc.xpath('//a[@class="thumbnail"]//img')
        for img in thumb_els:
            src = img.get("src") or img.get("data-src", "")
            if src:
                media.append({"type": "image", "url": unescape(src), "role": "thumbnail"})
                break

        # Image/video link in post
        post_url = ""
        link_el = doc.xpath('//a[@data-event-action="title"]')
        if link_el:
            post_url = link_el[0].get("href", "")
        if not post_url:
            link_els = doc.xpath('//div[@class="usertext-body"]//a[@href]')
            for a in link_els:
                href = a.get("href", "")
                if href and not href.startswith("/") and "reddit.com" not in href:
                    post_url = href
                    break

        if post_url:
            ext = post_url.rsplit("?", 1)[0].lower()
            if any(ext.endswith(e) for e in (".jpg", ".jpeg", ".png", ".gif", ".webp")):
                media.append({"type": "image", "url": unescape(post_url), "role": "content"})
            elif "v.redd.it" in post_url:
                media.append({"type": "video", "url": post_url, "role": "content"})

        # ─── Metadata ───────────────────────────────────────────────────────
        metadata = {
            "url": final_url,
            "subreddit": subreddit,
            "author": author,
            "score": score,
            "num_comments": num_comments,
            "permalink": f"https://reddit.com{permalink}" if permalink else final_url,
            "created_utc": created_utc,
            "comment_count_fetched": len(comment_bucket),
            "comment_count_total": num_comments,
        }
        if flair:
            metadata["flair"] = flair

        # Crosspost detection
        xpost_el = doc.xpath('//span[contains(@class,"crosspost")]')
        if xpost_el:
            metadata["crosspost_from"] = xpost_el[0].text_content().strip()

        return ProcessorResult(
            title=f"[r/{subreddit}] {title_text}" if subreddit else title_text,
            description=selftext[:300] if selftext else None,
            content=None,
            raw_content=raw_html[:100000],
            media=media,
            metadata=metadata,
            source_platform="reddit",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )


# ─── Comment field extractors (used in the sections loop) ───────────────────

def _cel_author(thing_el) -> str:
    # Live format: data-author on thing
    author = thing_el.get("data-author", "")
    if author:
        return author
    # Fixture format: a.author descendant
    a = thing_el.find('.//a[@class="author"]')
    return a.text_content().strip() if a is not None else ""


def _cel_score(thing_el) -> int:
    # Live format: data-score on thing
    val = thing_el.get("data-score", "")
    if val and val.lstrip("-").isdigit():
        return int(val)
    # Fixture format: span.score descendant
    sp = thing_el.find('.//span[@class="score"]')
    if sp is not None:
        v = sp.get("data-score", "")
        if v.lstrip("-").isdigit():
            return int(v)
    return 0


def _find_child(el, xpath_str):
    """Execute xpath on element (handles ElementPath limitations)."""
    return el.xpath(xpath_str)


def _cel_body(thing_el) -> str:
    bodies = thing_el.xpath('.//div[contains(@class,"usertext-body")]')
    if bodies:
        return _strip_html(bodies[0].text_content() or "")
    return ""


def _cel_permalink(thing_el) -> str | None:
    # Live format: data-permalink on thing
    p = thing_el.get("data-permalink", "")
    if p:
        return f"https://reddit.com{p}"
    # Fixture format: a[data-permalink]
    a = thing_el.find('.//a[@data-permalink="true"]')
    if a is not None:
        href = a.get("href", "")
        if href.startswith("/"):
            return f"https://reddit.com{href}"
        return href
    return None


def _cel_created(thing_el) -> str | None:
    # Live format: data-timestamp on thing
    ts = thing_el.get("data-timestamp", "")
    if ts and ts.isdigit():
        return str(int(int(ts) / 1000))
    # Fixture format: time[@datetime]
    t = thing_el.find('.//time[@datetime]')
    if t is not None:
        dt = t.get("datetime", "")
        try:
            from datetime import datetime
            return str(int(datetime.fromisoformat(dt.replace("Z", "+00:00")).timestamp()))
        except Exception:
            pass
    return None


def _cel_is_submitter(thing_el) -> bool:
    bodies = thing_el.xpath('.//div[contains(@class,"usertext-body")]')
    if bodies:
        return bodies[0].xpath('.//span[@class="submitter"]') is not None
    return False
