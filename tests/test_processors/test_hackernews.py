"""Tests for Hacker News processor extract() and edge cases."""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest
import respx

from fourdpocket.processors.hackernews import (
    HackerNewsProcessor,
    _extract_item_id,
    _walk,
)

# ─── URL pattern matching ────────────────────────────────────────────────────


class TestURLPatternMatching:
    """Processor matches expected URL patterns."""

    @pytest.mark.parametrize("url,expected_id", [
        ("https://news.ycombinator.com/item?id=12345", "12345"),
        ("https://news.ycombinator.com/item?id=1&next=next", "1"),
        ("https://hn.algolia.com/api/v1/items/999", None),  # API URL not matched
    ])
    def test_extracts_item_id_from_url(self, url: str, expected_id: str | None):
        assert _extract_item_id(url) == expected_id

    @pytest.mark.parametrize("url", [
        "https://news.ycombinator.com/item?id=12345",
        "https://news.ycombinator.com/item?id=1&next=prev",
    ])
    def test_matches_hackernews_url_patterns(self, url: str):
        proc = HackerNewsProcessor()
        matches = any(re.search(p, url) for p in proc.url_patterns)
        assert matches, f"URL did not match: {url}"


HN_API_PAYLOAD = {
    "id": 12345,
    "title": "Show HN: I built a new programming language",
    "author": "lang_author",
    "points": 300,
    "text": "It compiles to WASM and has a great type system.",
    "url": "https://example.com/new-lang",
    "created_at": "2026-01-01T10:00:00Z",
    "children": [
        {
            "id": 101, "type": "comment", "author": "commenter1",
            "text": "This looks promising!", "points": 50,
            "created_at": "2026-01-01T11:00:00Z",
            "children": [
                {
                    "id": 102, "type": "comment", "author": "reply_author",
                    "text": "Agreed, the syntax is clean.", "points": 20,
                    "children": [],
                },
            ],
        },
        {
            "id": 103, "type": "comment", "author": "skeptic",
            "text": "How does it compare to Rust?", "points": 80,
            "created_at": "2026-01-01T12:00:00Z",
            "children": [],
        },
        {
            "id": 104, "type": "comment", "author": "empty_comment",
            "text": "", "points": 0,
            "children": [],
        },
    ],
}


class TestExtract:
    """Test the HackerNewsProcessor.process() method."""

    @respx.mock(assert_all_called=False)
    def test_extract_success(self):
        """Happy path: valid HN URL returns ProcessorResult with sections."""
        proc = HackerNewsProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://hn.algolia.com/api/v1/items/12345").mock(
                return_value=httpx.Response(200, json=HN_API_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://news.ycombinator.com/item?id=12345")
            )

        assert result.source_platform == "hackernews"
        assert result.status.value == "success"
        assert "new programming language" in result.title

    @respx.mock(assert_all_called=False)
    def test_extract_404(self):
        """Item not found → partial status with error."""
        proc = HackerNewsProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://hn.algolia.com/api/v1/items/999999").mock(
                return_value=httpx.Response(404, json={"message": "Not found"})
            )
            result = asyncio.run(
                proc.process("https://news.ycombinator.com/item?id=999999")
            )

        assert result.status.value == "partial"
        assert "404" in result.error

    @respx.mock(assert_all_called=False)
    def test_extract_network_error(self):
        """Network error → graceful failure."""
        proc = HackerNewsProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://hn\.algolia\.com/api/v1/items/.*").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            result = asyncio.run(
                proc.process("https://news.ycombinator.com/item?id=12345")
            )

        assert result.status.value == "failed"
        assert result.error is not None

    def test_url_pattern_matching(self):
        """Processor correctly matches HN URL patterns."""
        proc = HackerNewsProcessor()
        url = "https://news.ycombinator.com/item?id=12345"
        matched = any(re.search(p, url) for p in proc.url_patterns)
        assert matched

    @respx.mock(assert_all_called=False)
    def test_extract_metadata(self):
        """Platform-specific metadata extracted correctly."""
        proc = HackerNewsProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://hn.algolia.com/api/v1/items/12345").mock(
                return_value=httpx.Response(200, json=HN_API_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://news.ycombinator.com/item?id=12345")
            )

        assert result.metadata.get("author") == "lang_author"
        assert result.metadata.get("score") == 300
        assert result.metadata.get("story_url") == "https://example.com/new-lang"
        assert result.metadata.get("item_id") == "12345"

    @respx.mock(assert_all_called=False)
    def test_sections_structure(self):
        """Extracted sections have correct kind, author, score, depth fields."""
        proc = HackerNewsProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://hn.algolia.com/api/v1/items/12345").mock(
                return_value=httpx.Response(200, json=HN_API_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://news.ycombinator.com/item?id=12345")
            )

        sections = result.sections
        # 1 post + 2 comments + 1 reply (empty comment skipped)
        assert len(sections) == 4

        post = next(s for s in sections if s.kind == "post")
        assert post.author == "lang_author"
        assert post.score == 300
        assert post.parent_id is None
        assert post.depth == 0
        assert post.role == "main"

        # Comments sorted by score descending
        comments = [s for s in sections if s.kind == "comment"]
        assert len(comments) == 2
        assert comments[0].author == "skeptic"  # 80 points > 50 points
        assert comments[0].score == 80
        assert comments[0].parent_id == post.id
        assert comments[0].depth == 1

        assert comments[1].author == "commenter1"
        assert comments[1].score == 50

        # Nested reply
        reply = next(s for s in sections if s.kind == "reply")
        assert reply.author == "reply_author"
        assert reply.depth == 2
        assert reply.parent_id == comments[1].id  # child of commenter1

    @respx.mock(assert_all_called=False)
    def test_selftext_in_post_section(self):
        """Selftext body is included in the post section."""
        proc = HackerNewsProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://hn.algolia.com/api/v1/items/12345").mock(
                return_value=httpx.Response(200, json=HN_API_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://news.ycombinator.com/item?id=12345")
            )

        post = next(s for s in result.sections if s.kind == "post")
        assert "programming language" in post.text
        assert "WASM" in post.text

    @respx.mock(assert_all_called=False)
    def test_ask_hn_detection(self):
        """Ask HN posts are flagged in post extra metadata."""
        proc = HackerNewsProcessor()

        ask_payload = {
            **HN_API_PAYLOAD,
            "title": "Ask HN: Best resources to learn Go?",
            "text": "I'm new to Go and looking for recommendations.",
        }

        with respx.mock(assert_all_called=False) as r:
            r.get("https://hn.algolia.com/api/v1/items/12345").mock(
                return_value=httpx.Response(200, json=ask_payload)
            )
            result = asyncio.run(
                proc.process("https://news.ycombinator.com/item?id=12345")
            )

        post = next(s for s in result.sections if s.kind == "post")
        assert post.extra.get("kind") == "ask"


class TestWalkComments:
    """Test the _walk helper for comment tree flattening."""

    def test_walk_sorts_by_score(self):
        """Comments are sorted by points descending."""
        children = [
            {"id": 1, "type": "comment", "text": "low", "points": 10, "children": []},
            {"id": 2, "type": "comment", "text": "high", "points": 100, "children": []},
            {"id": 3, "type": "comment", "text": "mid", "points": 50, "children": []},
        ]
        bucket: list[tuple] = []
        _walk(children, "parent", 1, bucket)
        texts = [c[0]["text"] for c in bucket]
        assert texts == ["high", "mid", "low"]  # sorted by score descending

    def test_walk_skips_empty_text(self):
        """Comments with empty text are skipped."""
        children = [
            {"id": 1, "type": "comment", "text": "", "points": 10, "children": []},
            {"id": 2, "type": "comment", "text": "valid", "points": 5, "children": []},
        ]
        bucket: list[tuple] = []
        _walk(children, "parent", 1, bucket)
        assert len(bucket) == 1
        assert bucket[0][0]["text"] == "valid"

    def test_walk_respects_max_depth(self):
        """Walking stops at max depth."""
        # _MAX_DEPTH = 6; check is `depth > _MAX_DEPTH`, so depth 6 IS allowed
        # Start at depth 7 to verify depth 7 items are blocked
        deep = {"id": 1, "type": "comment", "text": "deep", "points": 1,
                "children": [{"id": 2, "type": "comment", "text": "deeper", "points": 1, "children": []}]}
        bucket: list[tuple] = []
        _walk([deep], "parent", 7, bucket)  # starting at depth 7 (blocked)
        assert len(bucket) == 0  # should not descend past _MAX_DEPTH=6

    def test_walk_respects_max_comments(self):
        """Walking stops after _MAX_COMMENTS entries."""
        many = [{"id": i, "type": "comment", "text": f"c{i}", "points": 1, "children": []}
               for i in range(100)]
        bucket: list[tuple] = []
        _walk(many, "parent", 1, bucket)
        assert len(bucket) == 80  # capped at _MAX_COMMENTS

    def test_walk_only_comments_not_jobs(self):
        """Only type=comment nodes are included, not 'job' type."""
        children = [
            {"id": 1, "type": "comment", "text": "a comment", "points": 1, "children": []},
            {"id": 2, "type": "job", "text": "a job", "points": 0, "children": []},
        ]
        bucket: list[tuple] = []
        _walk(children, "parent", 1, bucket)
        assert len(bucket) == 1
        assert bucket[0][0]["type"] == "comment"
