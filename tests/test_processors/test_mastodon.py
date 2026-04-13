"""Tests for Mastodon Fediverse processor."""
import asyncio

import respx
from httpx import Response

from fourdpocket.processors.mastodon import MastodonProcessor, _strip_html


class TestExtract:
    """Test the extract() method with mocked HTTP responses."""

    @respx.mock
    def test_extract_success_with_context(self):
        """Mastodon status with context (ancestors + descendants) → full thread."""
        processor = MastodonProcessor()
        url = "https://fosstodon.org/@alice/1234567890"

        # Mock status API
        status_response = {
            "id": "1234567890",
            "content": "<p>Hello world! This is my toot.</p>",
            "account": {
                "acct": "alice",
                "display_name": "Alice Smith",
            },
            "favourites_count": 42,
            "reblogs_count": 10,
            "replies_count": 5,
            "created_at": "2024-01-15T10:00:00Z",
            "language": "en",
            "url": "https://fosstodon.org/@alice/1234567890",
            "media_attachments": [
                {
                    "type": "image",
                    "url": "https://media.example.com/image.jpg",
                    "preview_url": "https://media.example.com/preview.jpg",
                    "description": "A beautiful sunset over mountains",
                }
            ],
            "spoiler_text": "",
        }

        context_response = {
            "ancestors": [
                {
                    "id": "111",
                    "content": "<p>Original post that I'm replying to.</p>",
                    "account": {"acct": "bob", "display_name": "Bob Jones"},
                    "favourites_count": 10,
                    "created_at": "2024-01-15T09:00:00Z",
                    "url": "https://fosstodon.org/@bob/111",
                }
            ],
            "descendants": [
                {
                    "id": "222",
                    "content": "<p>Great toot! Loved it.</p>",
                    "account": {"acct": "charlie", "display_name": "Charlie"},
                    "favourites_count": 5,
                    "created_at": "2024-01-15T11:00:00Z",
                    "url": "https://fosstodon.org/@charlie/222",
                    "in_reply_to_id": "1234567890",
                }
            ],
        }

        respx.get(
            url__regex=r"https://fosstodon\.org/api/v1/statuses/1234567890$"
        ).mock(return_value=Response(200, json=status_response))
        respx.get(
            url__regex=r"https://fosstodon\.org/api/v1/statuses/1234567890/context"
        ).mock(return_value=Response(200, json=context_response))

        result = asyncio.run(processor.process(url))

        assert result.status.value == "success"
        assert result.source_platform == "mastodon"
        assert "Alice Smith" in result.title
        assert result.metadata["instance"] == "fosstodon.org"
        assert result.metadata["status_id"] == "1234567890"
        assert result.metadata["boosts_count"] == 10
        assert result.metadata["favourites_count"] == 42
        assert result.metadata["ancestor_count"] == 1
        assert result.metadata["descendant_count_fetched"] == 1
        # Check sections: ancestor, main post, visual_caption, reply
        section_kinds = [s.kind for s in result.sections]
        assert "reply" in section_kinds  # ancestor
        assert "post" in section_kinds  # main toot
        assert "visual_caption" in section_kinds  # alt text
        assert "reply" in section_kinds  # descendant
        # Check media
        assert len(result.media) == 1
        assert result.media[0]["type"] == "image"

    @respx.mock
    def test_extract_reblog(self):
        """Boosted status is unwrapped to original."""
        processor = MastodonProcessor()
        url = "https://hachyderm.io/@admin/999"

        status_response = {
            "id": "999",
            "content": "",
            "account": {"acct": "admin", "display_name": "Admin"},
            "favourites_count": 0,
            "reblogs_count": 5,
            "replies_count": 0,
            "created_at": "2024-01-15T12:00:00Z",
            "url": "https://hachyderm.io/@admin/999",
            "reblog": {
                "id": "888",
                "content": "<p>This is a boosted toot from someone else.</p>",
                "account": {"acct": "otheruser", "display_name": "Other User"},
                "favourites_count": 100,
                "reblogs_count": 20,
                "replies_count": 10,
                "created_at": "2024-01-15T11:00:00Z",
                "url": "https://hachyderm.io/@otheruser/888",
            },
        }

        respx.get(url__regex=r"https://hachyderm\.io/api/v1/statuses/999").mock(
            return_value=Response(200, json=status_response)
        )
        respx.get(url__regex=r"https://hachyderm\.io/api/v1/statuses/999/context").mock(
            return_value=Response(200, json={"ancestors": [], "descendants": []})
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "success"
        # Should be unwrapped to original
        assert result.metadata["status_id"] == "888"

    @respx.mock
    def test_extract_http_error(self):
        """HTTP error fetching status → partial result."""
        processor = MastodonProcessor()
        url = "https://mastodon.social/@user/123456"

        respx.get(url__regex=r"https://mastodon\.social/api/v1/statuses/123456").mock(
            return_value=Response(404)
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "partial"
        assert "404" in result.error

    @respx.mock
    def test_extract_network_error(self):
        """Network error → failed result."""
        processor = MastodonProcessor()
        url = "https://infosec.exchange/@researcher/777"

        respx.get(url__regex=r"https://infosec\.exchange/api/v1/statuses/777").mock(
            side_effect=Exception("Connection refused")
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "failed"

    @respx.mock
    def test_extract_context_fails_gracefully(self):
        """Context endpoint fails (rate-limited) — still returns main toot."""
        processor = MastodonProcessor()
        url = "https://mastodon.cloud/@poster/555"

        status_response = {
            "id": "555",
            "content": "<p>Main toot content.</p>",
            "account": {"acct": "poster", "display_name": "Poster"},
            "favourites_count": 5,
            "reblogs_count": 1,
            "replies_count": 2,
            "created_at": "2024-01-15T10:00:00Z",
            "url": "https://mastodon.cloud/@poster/555",
        }

        respx.get(url__regex=r"https://mastodon\.cloud/api/v1/statuses/555$").mock(
            return_value=Response(200, json=status_response)
        )
        respx.get(url__regex=r"https://mastodon\.cloud/api/v1/statuses/555/context").mock(
            side_effect=Exception("Rate limited")
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "success"
        # Main toot still present
        section_kinds = [s.kind for s in result.sections]
        assert "post" in section_kinds

    def test_extract_invalid_url(self):
        """Non-Mastodon URL → failed result."""
        processor = MastodonProcessor()
        url = "https://twitter.com/user/status/123"

        result = asyncio.run(processor.process(url))

        assert result.status.value == "failed"
        assert "parse" in result.error.lower()

    def test_strip_html(self):
        """HTML stripped to plain text - only p/br get newlines."""
        assert "Hello" in _strip_html("<p>Hello</p>")
        assert "world" in _strip_html("Hello<br>world")
        # _strip_html preserves content, just strips tags
        assert "bad" in _strip_html("<script>bad</script>")
        assert _strip_html("") == ""

    def test_url_pattern_matching(self):
        """Processor URL regex patterns match expected URLs via match_processor."""
        from fourdpocket.processors.registry import match_processor

        proc = match_processor("https://mastodon.social/@user/123456")
        assert type(proc).__name__ == "MastodonProcessor"

        proc = match_processor("https://fosstodon.org/@alice/987654321")
        assert type(proc).__name__ == "MastodonProcessor"
