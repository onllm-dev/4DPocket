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


REDDIT_POST_PAYLOAD = [
    {
        "data": {
            "children": [{
                "kind": "t3",
                "data": {
                    "id": "post1",
                    "title": "Best Python tips for beginners?",
                    "selftext": "I'm learning Python and would love tips.",
                    "subreddit": "python",
                    "author": "python_newbie",
                    "score": 150,
                    "num_comments": 25,
                    "permalink": "/r/python/comments/post1/title/",
                    "created_utc": 1700000000,
                    "is_self": True,
                    "link_flair_text": "Question",
                },
            }],
        },
    },
    {
        "data": {
            "children": [
                {
                    "kind": "t1",
                    "data": {
                        "id": "c1",
                        "author": "senior_dev",
                        "body": "Read the official tutorial first.",
                        "score": 80,
                        "permalink": "/r/python/comments/post1/title/c1/",
                        "created_utc": 1700000100,
                        "replies": {"data": {"children": [
                            {
                                "kind": "t1",
                                "data": {
                                    "id": "r1",
                                    "author": "python_newbie",
                                    "body": "Thanks! Will do.",
                                    "score": 5,
                                    "permalink": "/r/python/comments/post1/title/r1/",
                                },
                            },
                        ]}},
                    },
                },
                {
                    "kind": "t1",
                    "data": {
                        "id": "c2",
                        "author": "another_user",
                        "body": "I recommend the book 'Fluent Python'.",
                        "score": 200,
                        "permalink": "/r/python/comments/post1/title/c2/",
                        "created_utc": 1700000200,
                    },
                },
                # deleted comment should be skipped
                {"kind": "t1", "data": {"id": "del1", "author": "x", "body": "[deleted]", "score": 0}},
                # 'more' continuation should be ignored
                {"kind": "more", "data": {"children": ["c5", "c6"]}},
            ],
        },
    },
]


class TestExtract:
    """Test the RedditProcessor.process() method."""

    @respx.mock(assert_all_called=False)
    def test_extract_success(self):
        """Happy path: valid Reddit URL returns ProcessorResult with sections."""
        proc = RedditProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/post1/title\.json.*").mock(
                return_value=httpx.Response(200, json=REDDIT_POST_PAYLOAD)
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
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/notfound.*\.json.*").mock(
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
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/post1/title\.json.*").mock(
                return_value=httpx.Response(200, json=REDDIT_POST_PAYLOAD)
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
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/post1/title\.json.*").mock(
                return_value=httpx.Response(200, json=REDDIT_POST_PAYLOAD)
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
            r.get(url__regex=r"https://old\.reddit\.com/r/python/comments/post1/title\.json.*").mock(
                return_value=httpx.Response(200, json=REDDIT_POST_PAYLOAD)
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

        # Payload with thumbnail
        payload_with_thumb = [
            {
                "data": {
                    "children": [{
                        "kind": "t3",
                        "data": {
                            "id": "post2",
                            "title": "Check out this image",
                            "selftext": "",
                            "subreddit": "pics",
                            "author": "user1",
                            "score": 10,
                            "num_comments": 1,
                            "permalink": "/r/pics/comments/post2/title/",
                            "created_utc": 1700000000,
                            "is_self": False,
                            "thumbnail": "https://i.redd.it/thumb.jpg",
                            "url": "https://i.redd.it/image.jpg",
                        },
                    }],
                },
            },
            {"data": {"children": []}},
        ]

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/pics/comments/post2/title\.json.*").mock(
                return_value=httpx.Response(200, json=payload_with_thumb)
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

        payload_with_crosspost = [
            {
                "data": {
                    "children": [{
                        "kind": "t3",
                        "data": {
                            "id": "xpost1",
                            "title": "Interesting find",
                            "selftext": "",
                            "subreddit": "r/Programming",
                            "author": "user1",
                            "score": 50,
                            "num_comments": 5,
                            "permalink": "/r/Programming/comments/xpost1/title/",
                            "created_utc": 1700000000,
                            "is_self": True,
                            "crosspost_parent_list": [
                                {"subreddit_name_prefixed": "r/original"}
                            ],
                        },
                    }],
                },
            },
            {"data": {"children": []}},
        ]

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://old\.reddit\.com/r/Programming/comments/xpost1/title\.json.*").mock(
                return_value=httpx.Response(200, json=payload_with_crosspost)
            )
            result = asyncio.run(
                proc.process("https://www.reddit.com/r/Programming/comments/xpost1/title/")
            )

        assert result.metadata.get("crosspost_from") == "r/original"
