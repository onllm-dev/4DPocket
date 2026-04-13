"""Tests for Substack newsletter processor."""
import asyncio

import respx
from httpx import Response

from fourdpocket.processors.substack import (
    SubstackProcessor,
    _extract_pub_and_slug,
    _html_to_sections,
)


class TestExtract:
    """Test the extract() method with mocked HTTP responses."""

    @respx.mock
    def test_extract_via_api(self):
        """Substack API returns clean body_html."""
        processor = SubstackProcessor()
        url = "https://technews.substack.com/p/the-future-of-ai"

        api_response = {
            "title": "The Future of AI",
            "subtitle": "Exploring artificial intelligence trends",
            "body_html": "<h2>Introduction</h2><p>AI is transforming...</p><blockquote>Important quote</blockquote>",
            "cover_image": "https://example.com/cover.jpg",
            "post_date": "2024-01-15T10:00:00Z",
            "reactions": 150,
            "comment_count": 42,
            "wordcount": 1200,
            "publishedBylines": [{"name": "Jane Smith"}],
            "postTags": [{"name": "ai"}, {"name": "technology"}],
        }

        respx.get(
            url__regex=r"https://technews\.substack\.com/api/v1/posts/the-future-of-ai"
        ).mock(return_value=Response(200, json=api_response))

        result = asyncio.run(processor.process(url))

        assert result.status.value == "success"
        assert result.title == "The Future of AI"
        assert result.source_platform == "substack"
        assert result.metadata["author"] == "Jane Smith"
        assert result.metadata["newsletter_name"] == "technews"
        assert result.metadata["publication"] == "technews"
        assert result.metadata["reactions"] == 150
        assert "ai" in result.metadata["tags"]
        # Check sections have heading, paragraph, quote
        section_kinds = [s.kind for s in result.sections]
        assert "heading" in section_kinds
        assert "paragraph" in section_kinds
        assert "quote" in section_kinds

    @respx.mock
    def test_extract_substack_home_post(self):
        """Substack aggregator URL (substack.com/home/post/) extracts correctly."""
        processor = SubstackProcessor()
        url = "https://substack.com/home/post/p-12345678"

        # API won't match this pattern, falls back to HTML path
        respx.get(url).mock(
            return_value=Response(
                200,
                text="""<!DOCTYPE html>
<html>
<head><title>Home Post</title></head>
<body>
<article>
<p>This is a post from the Substack home feed.</p>
</article>
</body>
</html>"""
            )
        )

        result = asyncio.run(processor.process(url))

        # Falls back to trafilatura/OG extraction
        assert result.source_platform == "substack"
        assert result.status.value in ("success", "partial")

    @respx.mock
    def test_extract_api_404(self):
        """API returns 404, falls back to HTML."""
        processor = SubstackProcessor()
        url = "https://unknown.substack.com/p/nonexistent"

        respx.get(url__regex=r"https://unknown\.substack\.com/api/v1/posts/nonexistent").mock(
            return_value=Response(404)
        )
        # Fallback fetch
        respx.get(url).mock(
            return_value=Response(
                200,
                text="""<!DOCTYPE html><html><head><title>Unknown Post</title></head>
                <body><p>Post content here.</p></body></html>"""
            )
        )

        result = asyncio.run(processor.process(url))

        # Should fall back to HTML path
        assert result.source_platform == "substack"
        assert result.status.value in ("success", "partial")

    @respx.mock
    def test_extract_http_error(self):
        """HTTP error fetching HTML → partial result."""
        processor = SubstackProcessor()
        url = "https://news.substack.com/p/test"

        respx.get(url__regex=r"https://news\.substack\.com/api/v1/posts/test").mock(
            return_value=Response(404)
        )
        respx.get(url).mock(return_value=Response(500))

        result = asyncio.run(processor.process(url))

        assert result.status.value in ("partial", "failed")
        assert result.error is not None

    @respx.mock
    def test_extract_network_error(self):
        """Network error on fallback → failed result."""
        processor = SubstackProcessor()
        url = "https://mysub.substack.com/p/test"

        respx.get(url__regex=r"https://mysub\.substack\.com/api/v1/posts/test").mock(
            side_effect=Exception("DNS failure")
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "failed"

    def test_extract_pub_and_slug(self):
        """URL parsing extracts publication and slug correctly."""
        pub, slug = _extract_pub_and_slug(
            "https://technews.substack.com/p/the-future"
        )
        assert pub == "technews"
        assert slug == "the-future"

        pub2, slug2 = _extract_pub_and_slug(
            "https://news.substack.com/p/my-slug-here"
        )
        assert pub2 == "news"
        assert slug2 == "my-slug-here"

        pub3, slug3 = _extract_pub_and_slug(
            "https://substack.com/home/post/p-12345678"
        )
        assert pub3 is None
        assert slug3 == "p-12345678"

        pub4, slug4 = _extract_pub_and_slug("https://example.com/notsubstack")
        assert pub4 is None
        assert slug4 is None

    def test_html_to_sections(self):
        """HTML body parsed into typed sections."""
        html = """
        <h1>Main Title</h1>
        <h2>Subtitle</h2>
        <p>First paragraph text.</p>
        <blockquote>A famous quote.</blockquote>
        <pre>def process_data(data):
    return data.transform()</pre>
        <ul><li>Item one</li><li>Item two</li></ul>
        """
        sections, order = _html_to_sections(html, "https://example.com", 0)

        section_kinds = [s.kind for s in sections]
        assert "heading" in section_kinds  # h1
        assert "heading" in section_kinds  # h2 (second heading)
        assert "paragraph" in section_kinds  # p
        assert "quote" in section_kinds  # blockquote
        assert "code" in section_kinds  # pre (>20 chars)
        assert "list_item" in section_kinds  # li
        # 7 sections total: h1, h2, p, blockquote, code, li, li
        assert len(sections) == 7

    def test_url_pattern_matching(self):
        """Processor URL regex patterns match expected URLs via match_processor."""
        from fourdpocket.processors.registry import match_processor

        proc = match_processor("https://technews.substack.com/p/my-post")
        assert type(proc).__name__ == "SubstackProcessor"

        proc = match_processor("https://substack.com/home/post/p-12345678")
        assert type(proc).__name__ == "SubstackProcessor"
