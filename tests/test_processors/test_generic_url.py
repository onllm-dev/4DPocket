"""Tests for Generic URL processor (fallback)."""
import asyncio

import respx
from httpx import Response

from fourdpocket.processors.generic_url import GenericURLProcessor


class TestExtract:
    """Test the extract() method with mocked HTTP responses."""

    @respx.mock
    def test_extract_returns_result(self):
        """Generic URL with HTML → returns result."""
        processor = GenericURLProcessor()
        url = "https://httpbin.org/html"

        html_content = """<!DOCTYPE html>
<html>
<head>
<title>Example Article</title>
<meta name="description" content="An interesting article.">
<meta property="og:title" content="Example Article Title">
<meta property="og:image" content="https://example.com/cover.jpg">
</head>
<body>
<article>
<p>First paragraph of the article with enough content to pass the trafilatura threshold.</p>
<p>Second paragraph with more content that helps ensure we have enough text.</p>
<p>Third paragraph adds even more text to be well over the 200 character minimum for extraction.</p>
</article>
</body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.source_platform == "generic"
        assert result.status.value in ("success", "partial")

    @respx.mock
    def test_extract_non_html_content(self):
        """Non-HTML URL → partial with content type metadata."""
        processor = GenericURLProcessor()
        url = "https://httpbin.org/json"

        respx.get(url).mock(
            return_value=Response(
                200,
                text='{"key": "value"}',
                headers={"content-type": "application/json"},
            )
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "partial"
        assert "application/json" in result.description

    @respx.mock
    def test_extract_network_error(self):
        """Network error → failed result."""
        import httpx
        processor = GenericURLProcessor()
        url = "https://httpbin.org/delay/1"

        respx.get(url).mock(side_effect=httpx.RequestError("Connection timeout"))

        result = asyncio.run(processor.process(url))

        assert result.status.value == "failed"

    def test_url_pattern_matching(self):
        """GenericURLProcessor matches nothing (fallback only)."""
        processor = GenericURLProcessor()

        # GenericURLProcessor should NOT match any URL by pattern
        # It's the fallback for when no other processor matches
        assert processor.url_patterns == []
        assert processor.priority == -1


# === PHASE 2A MOPUP ADDITIONS ===


class TestGenericURLOgMetadata:
    """OG metadata extraction from HTML."""

    @respx.mock
    def test_extracts_og_title_and_description(self, respx_mock):
        """OG title, description, image extracted correctly."""
        url = "https://example.com/article"

        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="Example Article Title">
<meta property="og:description" content="This is the article description.">
<meta property="og:image" content="https://example.com/cover.jpg">
<meta property="og:site_name" content="Example Site">
<meta name="author" content="Jane Doe">
<meta name="keywords" content="python, programming, tutorial">
<link rel="icon" href="https://example.com/favicon.ico">
</head>
<body></body>
</html>"""

        respx_mock.get(url).mock(return_value=Response(200, text=html_content, headers={"content-type": "text/html"}))

        proc = GenericURLProcessor()
        result = asyncio.run(proc.process(url))

        assert result.title == "Example Article Title"
        assert result.description == "This is the article description."
        assert result.metadata.get("site_name") == "Example Site"
        assert result.metadata.get("author") == "Jane Doe"
        assert result.metadata.get("keywords") == "python, programming, tutorial"
        assert result.metadata.get("favicon") == "https://example.com/favicon.ico"
        assert any(m["url"] == "https://example.com/cover.jpg" for m in result.media)

    @respx.mock
    def test_fallback_to_html_title(self, respx_mock):
        """No OG title → falls back to <title> tag."""
        url = "https://example.com/no-og"

        html_content = """<!DOCTYPE html>
<html>
<head><title>Page Title From Title Tag</title></head>
<body></body>
</html>"""

        respx_mock.get(url).mock(return_value=Response(200, text=html_content, headers={"content-type": "text/html"}))

        proc = GenericURLProcessor()
        result = asyncio.run(proc.process(url))

        assert result.title == "Page Title From Title Tag"

    @respx.mock
    def test_extracts_json_ld(self, respx_mock):
        """JSON-LD extracted and capped at 5000 chars."""
        url = "https://example.com/jsonld"
        large_jsonld = '{"@type":"Article","name":"Test"}' + "x" * 5100

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<script type="application/ld+json">{large_jsonld}</script>
</head>
<body></body>
</html>"""

        respx_mock.get(url).mock(return_value=Response(200, text=html_content, headers={"content-type": "text/html"}))

        proc = GenericURLProcessor()
        result = asyncio.run(proc.process(url))

        assert "json_ld" in result.metadata
        assert len(result.metadata["json_ld"]) <= 5000


class TestGenericURLErrors:
    """Error handling paths."""

    @respx.mock
    def test_http_404_returns_partial(self, respx_mock):
        """HTTP 404 → partial, not failed."""
        url = "https://example.com/notfound"

        respx_mock.get(url).mock(return_value=Response(404))

        proc = GenericURLProcessor()
        result = asyncio.run(proc.process(url))

        assert result.status.value == "partial"
        assert "404" in result.error

    @respx.mock
    def test_http_500_returns_partial(self, respx_mock):
        """HTTP 500 → partial."""
        url = "https://example.com/error"

        respx_mock.get(url).mock(return_value=Response(500))

        proc = GenericURLProcessor()
        result = asyncio.run(proc.process(url))

        assert result.status.value == "partial"

    @respx.mock
    def test_timeout_returns_failed(self, respx_mock):
        """Request timeout → failed."""
        import httpx
        url = "https://example.com/slow"

        respx_mock.get(url).mock(side_effect=httpx.TimeoutException("timeout"))

        proc = GenericURLProcessor()
        result = asyncio.run(proc.process(url))

        assert result.status.value == "failed"
        assert "Request failed" in result.error


class TestGenericURLSections:
    """Sections structure when HTML extraction succeeds."""

    @respx.mock
    def test_sections_include_title(self, respx_mock):
        """Result includes sections with title when OG title present."""
        url = "https://example.com/sections"

        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="Section Test Article">
</head>
<body></body>
</html>"""

        respx_mock.get(url).mock(return_value=Response(200, text=html_content, headers={"content-type": "text/html"}))

        proc = GenericURLProcessor()
        result = asyncio.run(proc.process(url))

        section_kinds = {s.kind for s in result.sections}
        assert "title" in section_kinds
        title_section = next(s for s in result.sections if s.kind == "title")
        assert title_section.text == "Section Test Article"

    @respx.mock
    def test_non_html_returns_partial_with_content_type(self, respx_mock):
        """Non-HTML content type → partial."""
        url = "https://example.com/data.json"

        respx_mock.get(url).mock(
            return_value=Response(
                200,
                text='{"key": "value"}',
                headers={"content-type": "application/json"},
            )
        )

        proc = GenericURLProcessor()
        result = asyncio.run(proc.process(url))

        assert result.status.value == "partial"
        assert "content_type" in result.metadata
