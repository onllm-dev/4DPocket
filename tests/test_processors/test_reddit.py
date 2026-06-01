"""Tests for Reddit processor extract() and edge cases."""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest
import respx

from fourdpocket.processors.reddit import RedditProcessor

# ─── URL pattern matching ────────────────────────────────────────────────────


class TestURLPatternMatching:
    """Processor matches expected URL patterns."""

    @pytest.mark.parametrize("url", [
        "https://www.reddit.com/r/python/comments/abc123/title/",
        "https://old.reddit.com/r/programming/comments/def456/another/",
        "https://redd.it/shortcode",
    ])
    def test_matches_reddit_url_patterns(self, url: str):
        proc = RedditProcessor()
        matches = any(re.search(p, url) for p in proc.url_patterns)
        assert matches, f"URL did not match: {url}"


# ─── HTML fixtures ──────────────────────────────────────────────────────────

REDDIT_HTML_POST = """<!DOCTYPE html>
<html>
<head><title>Best Python tips for beginners? : r/python</title></head>
<body>
<div class="sitetable">
  <div class="entry" data-fullname="t3_post1" data-parent="">
    <a class="author">python_newbie</a>
    <a class="subreddit">r/python</a>
    <span class="score" data-score="150">150 points</span>
    <a class="comments" data-num-comments="25" href="/r/python/comments/post1/title/">25 comments</a>
    <span class="linkflairtext">Question</span>
    <div class="usertext-body">
      <p>I'm learning Python and would love tips.</p>
    </div>
    <a data-event-action="title" href="/r/python/comments/post1/title/">link</a>
    <time datetime="2023-11-14T12:00:00+00:00">2023-11-14</time>
  </div>
 <!-- comment1: senior_dev, score 80 -->
  <div class="entry" data-fullname="t1_c1" data-parent="post1">
    <a class="author">senior_dev</a>
    <span class="score" data-score="80">80 points</span>
    <div class="usertext-body"><p>Read the official tutorial first.</p></div>
    <a data-permalink="true" href="/r/python/comments/post1/title/c1/">permalink</a>
    <time datetime="2023-11-14T12:01:00+00:00">2023-11-14</time>
    <!-- nested reply: python_newbie, score 5 -->
    <div class="entry" data-fullname="t1_r1" data-parent="c1">
      <a class="author">python_newbie</a>
      <span class="score" data-score="5">5 points</span>
      <div class="usertext-body"><p>Thanks! Will do.</p></div>
      <a data-permalink="true" href="/r/python/comments/post1/title/r1/">permalink</a>
      <time datetime="2023-11-14T12:02:00+00:00">2023-11-14</time>
    </div>
  </div>
  <!-- comment 2: another_user, score 200 (top scored) -->
  <div class="entry" data-fullname="t1_c2" data-parent="post1">
    <a class="author">another_user</a>
    <span class="score" data-score="200">200 points</span>
    <div class="usertext-body"><p>I recommend the book 'Fluent Python'.</p></div>
    <a data-permalink="true" href="/r/python/comments/post1/title/c2/">permalink</a>
    <time datetime="2023-11-14T12:03:00+00:00">2023-11-14</time>
  </div>
  <!-- deleted comment should be skipped -->
  <div class="entry" data-fullname="t1_del1" data-parent="post1">
    <a class="author">deleted</a>
    <span class="score" data-score="0">0 points</span>
    <div class="usertext-body"><p>[deleted]</p></div>
  </div>
</div>
<link rel="canonical" href="https://www.reddit.com/r/python/comments/post1/title/">
</body></html>"""

REDDIT_HTML_THUMB = """<!DOCTYPE html>
<html>
<head><title>Check out this image : r/pics</title></head>
<body>
<div class="sitetable">
  <div class="entry" data-fullname="t3_post2" data-parent="">
    <a class="author">user1</a>
    <a class="subreddit">r/pics</a>
    <span class="score" data-score="10">10 points</span>
    <a class="comments" data-num-comments="1" href="/r/pics/comments/post2/title/">1 comment</a>
    <a class="thumbnail"><img src="https://i.redd.it/thumb.jpg"></a>
    <a data-event-action="title" href="https://i.redd.it/image.jpg">link</a>
    <time datetime="2023-11-14T12:00:00+00:00">2023-11-14</time>
  </div>
</div>
<link rel="canonical" href="https://www.reddit.com/r/pics/comments/post2/title/">
</body></html>"""

REDDIT_HTML_CROSSPOST = """<!DOCTYPE html>
<html>
<head><title>Interesting find : r/Programming</title></head>
<body>
<div class="sitetable">
  <div class="entry" data-fullname="t3_xpost1" data-parent="">
    <a class="author">user1</a>
    <a class="subreddit">r/Programming</a>
    <span class="score" data-score="50">50 points</span>
    <a class="comments" data-num-comments="5" href="/r/Programming/comments/xpost1/title/">5 comments</a>
    <span class="linkflairtext">Crosspost</span>
    <span class="crosspost">r/original</span>
    <div class="usertext-body"><p>See original post.</p></div>
    <time datetime="2023-11-14T12:00:00+00:00">2023-11-14</time>
  </div>
</div>
<link rel="canonical" href="https://www.reddit.com/r/Programming/comments/xpost1/title/">
</body></html>"""


class TestExtract:
    """Test the RedditProcessor.process() method."""

    @respx.mock(assert_all_called=False)
    def test_extract_success(self):
        """Happy path: valid Reddit URL returns ProcessorResult with sections."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/post1/title/").mock(
                return_value=httpx.Response(200, text=REDDIT_HTML_POST)
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/python/comments/post1/title/")
            )

        assert result.source_platform == "reddit"
        assert result.status.value == "success"
        assert "[r/python]" in result.title
        assert "Best Python tips" in result.title

    @respx.mock(assert_all_called=False)
    def test_extract_404(self):
        """URL returns 404 → partial status with error."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/notfound/").mock(
                return_value=httpx.Response(404)
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/python/comments/notfound/title/")
            )

        assert result.status.value == "partial"
        assert result.error is not None

    @respx.mock(assert_all_called=False)
    def test_extract_network_error(self):
        """Network timeout/error → graceful failure."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/.*").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/python/comments/post1/title/")
            )

        assert result.status.value == "failed"
        assert result.error is not None

    @respx.mock(assert_all_called=False)
    def test_extract_metadata(self):
        """Platform-specific metadata extracted correctly."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/post1/title/").mock(
                return_value=httpx.Response(200, text=REDDIT_HTML_POST)
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/python/comments/post1/title/")
            )

        assert result.metadata.get("subreddit") == "python"
        assert result.metadata.get("author") == "python_newbie"
        assert result.metadata.get("score") == 150
        assert result.metadata.get("num_comments") == 25
        assert result.metadata.get("flair") == "Question"
        assert result.metadata.get("comment_count_fetched") == 3  # c1, c2, r1 (deleted skipped)

    @respx.mock(assert_all_called=False)
    def test_sections_structure(self):
        """Extracted sections have correct kind, content, author fields."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/post1/title/").mock(
                return_value=httpx.Response(200, text=REDDIT_HTML_POST)
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/python/comments/post1/title/")
            )

        sections = result.sections
        # 1 post + 2 top-level comments (deleted skipped) + 1 nested reply
        assert sum(1 for s in sections if s.kind == "post") == 1
        assert sum(1 for s in sections if s.kind == "comment") == 2
        assert sum(1 for s in sections if s.kind == "reply") == 1

        post = next(s for s in sections if s.kind == "post")
        assert post.author == "python_newbie"
        assert post.score == 150
        assert post.parent_id is None
        assert post.extra.get("subreddit") == "python"
        assert post.extra.get("flair") == "Question"

        # Top-scored comment first (score-weighted)
        comments = [s for s in sections if s.kind == "comment"]
        assert comments[0].author == "another_user"  # 200 score
        assert comments[0].score == 200
        assert comments[0].parent_id == post.id

        reply = next(s for s in sections if s.kind == "reply")
        assert reply.depth == 2
        assert reply.parent_id == comments[1].id  # r1 is child of c1 (senior_dev, score 80)

    @respx.mock(assert_all_called=False)
    def test_selftext_in_post_section(self):
        """Selftext body is included in the post section text."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/post1/title/").mock(
                return_value=httpx.Response(200, text=REDDIT_HTML_POST)
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/python/comments/post1/title/")
            )

        post = next(s for s in result.sections if s.kind == "post")
        assert "I'm learning Python" in post.text

    @respx.mock(assert_all_called=False)
    def test_media_extraction(self):
        """Media (thumbnail) is extracted into ProcessorResult.media."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/pics/comments/post2/title/").mock(
                return_value=httpx.Response(200, text=REDDIT_HTML_THUMB)
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/pics/comments/post2/title/")
            )

        assert len(result.media) >= 1
        thumb = next((m for m in result.media if m.get("role") == "thumbnail"), None)
        assert thumb is not None
        assert "thumb.jpg" in thumb["url"]

    @respx.mock(assert_all_called=False)
    def test_crosspost_metadata(self):
        """Crosspost source is captured in metadata."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/Programming/comments/xpost1/title/").mock(
                return_value=httpx.Response(200, text=REDDIT_HTML_CROSSPOST)
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/Programming/comments/xpost1/title/")
            )

        assert result.metadata.get("crosspost_from") == "r/original"
