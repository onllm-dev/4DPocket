"""Tests for Twitter processor extract() and edge cases."""

from __future__ import annotations

import asyncio
import re

import httpx
import pytest
import respx

from fourdpocket.processors.twitter import (
    TwitterProcessor,
    _extract_tweet_id,
    _extract_username,
)

# ─── URL pattern matching ────────────────────────────────────────────────────


class TestURLPatternMatching:
    """Processor matches expected URL patterns."""

    @pytest.mark.parametrize("url,expected_id", [
        ("https://twitter.com/someuser/status/1234567890", "1234567890"),
        ("https://x.com/someuser/status/1234567890", "1234567890"),
        ("https://mobile.twitter.com/someuser/status/1234567890", "1234567890"),
    ])
    def test_extracts_tweet_id(self, url: str, expected_id: str):
        assert _extract_tweet_id(url) == expected_id

    @pytest.mark.parametrize("url,expected_username", [
        ("https://twitter.com/someuser/status/123", "someuser"),
        ("https://x.com/AnotherUser/status/456", "AnotherUser"),
    ])
    def test_extracts_username(self, url: str, expected_username: str):
        assert _extract_username(url) == expected_username

    @pytest.mark.parametrize("url", [
        "https://twitter.com/someuser/status/1234567890",
        "https://x.com/someuser/status/1234567890",
    ])
    def test_matches_twitter_url_patterns(self, url: str):
        proc = TwitterProcessor()
        matches = any(re.search(p, url) for p in proc.url_patterns)
        assert matches, f"URL did not match: {url}"

    def test_unknown_url_returns_none(self):
        assert _extract_tweet_id("https://example.com/post/123") is None


FX_TWEET_PAYLOAD = {
    "tweet": {
        "text": "Hot take: Python dicts are amazing.",
        "created_at": "2026-01-01T12:00:00Z",
        "lang": "en",
        "likes": 1234,
        "retweets": 200,
        "replies": 50,
        "author": {
            "name": "Python Dev", "screen_name": "pythondev",
            "followers": 10000, "avatar_url": "https://pbs.twimg.com/avatar.jpg",
        },
        "media": {"all": [
            {"type": "photo", "url": "https://pbs.twimg.com/media/abc.jpg"},
        ]},
        "quote": {
            "text": "Original quote I'm responding to",
            "author": {"name": "Other Dev", "screen_name": "otherdev", "followers": 500},
            "likes": 100,
        },
    },
}


class TestExtract:
    """Test the TwitterProcessor.process() method."""

    @respx.mock(assert_all_called=False)
    def test_extract_success(self):
        """Happy path: valid tweet URL returns ProcessorResult with sections."""
        proc = TwitterProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.fxtwitter.com/pythondev/status/1234567890").mock(
                return_value=httpx.Response(200, json=FX_TWEET_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://twitter.com/pythondev/status/1234567890")
            )

        assert result.source_platform == "twitter"
        assert result.status.value == "success"
        assert "pythondev" in result.title

    @respx.mock(assert_all_called=False)
    def test_extract_404(self):
        """Tweet not found → partial status with error."""
        proc = TwitterProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.fxtwitter.com/user/status/9999999999").mock(
                return_value=httpx.Response(404, json={"error": "not found"})
            )
            result = asyncio.run(
                proc.process("https://twitter.com/user/status/9999999999")
            )

        assert result.status.value == "partial"
        assert "unavailable" in result.error.lower() or "not found" in result.error.lower()

    @respx.mock(assert_all_called=False)
    def test_extract_network_error(self):
        """Network error → graceful failure."""
        proc = TwitterProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get(url__regex=r"https://api\.fxtwitter\.com/.*").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            result = asyncio.run(
                proc.process("https://twitter.com/pythondev/status/1234567890")
            )

        assert result.status.value == "partial"
        assert result.error is not None

    def test_url_pattern_matching(self):
        """Processor correctly matches Twitter/X URL patterns."""
        proc = TwitterProcessor()
        url = "https://x.com/someuser/status/1234567890"
        matched = any(re.search(p, url) for p in proc.url_patterns)
        assert matched

    @respx.mock(assert_all_called=False)
    def test_extract_metadata(self):
        """Platform-specific metadata extracted correctly."""
        proc = TwitterProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.fxtwitter.com/pythondev/status/1234567890").mock(
                return_value=httpx.Response(200, json=FX_TWEET_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://twitter.com/pythondev/status/1234567890")
            )

        assert result.metadata.get("author_handle") == "pythondev"
        assert result.metadata.get("author_name") == "Python Dev"
        assert result.metadata.get("likes") == 1234
        assert result.metadata.get("retweets") == 200
        assert result.metadata.get("replies") == 50
        assert result.metadata.get("author_followers") == 10000
        assert result.metadata.get("language") == "en"
        assert result.metadata.get("quote_author") == "otherdev"

    @respx.mock(assert_all_called=False)
    def test_sections_structure(self):
        """Extracted sections have correct kind, author, score fields."""
        proc = TwitterProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.fxtwitter.com/pythondev/status/1234567890").mock(
                return_value=httpx.Response(200, json=FX_TWEET_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://twitter.com/pythondev/status/1234567890")
            )

        sections = result.sections
        assert len(sections) == 2  # main post + quoted_post

        main = next(s for s in sections if s.kind == "post")
        assert main.author == "pythondev"
        assert main.score == 1234
        assert main.parent_id is None
        assert main.role == "main"
        assert "Python dicts are amazing" in main.text

        quoted = next(s for s in sections if s.kind == "quoted_post")
        assert quoted.author == "otherdev"
        assert quoted.parent_id == main.id
        assert quoted.score == 100
        assert quoted.depth == 1

    @respx.mock(assert_all_called=False)
    def test_media_extraction(self):
        """Media is extracted into ProcessorResult.media."""
        proc = TwitterProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.fxtwitter.com/pythondev/status/1234567890").mock(
                return_value=httpx.Response(200, json=FX_TWEET_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://twitter.com/pythondev/status/1234567890")
            )

        assert len(result.media) >= 1
        photo = next((m for m in result.media if m.get("type") == "image"), None)
        assert photo is not None
        assert "abc.jpg" in photo["url"]

    @respx.mock(assert_all_called=False)
    def test_retweet_metrics(self):
        """Retweet and reply counts are captured."""
        proc = TwitterProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.fxtwitter.com/pythondev/status/1234567890").mock(
                return_value=httpx.Response(200, json=FX_TWEET_PAYLOAD)
            )
            result = asyncio.run(
                proc.process("https://twitter.com/pythondev/status/1234567890")
            )

        assert result.metadata.get("retweets") == 200
        assert result.metadata.get("replies") == 50


class TestTweetWithoutQuote:
    """Test tweet extraction when there is no quoted tweet."""

    @respx.mock(assert_all_called=False)
    def test_tweet_without_quote(self):
        """Tweet without quoted post still returns success."""
        proc = TwitterProcessor()

        simple_payload = {
            "tweet": {
                "text": "Just a simple tweet.",
                "created_at": "2026-01-01T12:00:00Z",
                "lang": "en",
                "likes": 10,
                "retweets": 2,
                "replies": 1,
                "author": {
                    "name": "User", "screen_name": "user",
                    "followers": 100, "avatar_url": "",
                },
                "media": {"all": []},
            },
        }

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.fxtwitter.com/user/status/111").mock(
                return_value=httpx.Response(200, json=simple_payload)
            )
            result = asyncio.run(
                proc.process("https://twitter.com/user/status/111")
            )

        assert result.status.value == "success"
        sections = result.sections
        assert len(sections) == 1
        assert sections[0].kind == "post"
        assert "simple tweet" in sections[0].text
