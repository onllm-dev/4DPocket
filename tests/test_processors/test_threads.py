"""Tests for Threads (Meta) processor."""
import asyncio

import respx
from httpx import Response

from fourdpocket.processors.threads import ThreadsProcessor


class TestExtract:
    """Test the extract() method with mocked HTTP responses."""

    @respx.mock
    def test_extract_success_with_trafilatura(self):
        """Threads post extracted via trafilatura → success."""
        processor = ThreadsProcessor()
        url = "https://threads.net/@username/post/1234567890123456789"

        html_content = """<!DOCTYPE html>
<html>
<head>
<title>Username's Thread</title>
<meta property="og:title" content="Thread by @username">
<meta property="og:description" content="My thoughts on this topic...">
<meta property="og:image" content="https://example.com/thread-thumb.jpg">
<meta property="og:site_name" content="Threads">
</head>
<body>
<article>
<p>This is the full text of my thread about interesting topics.</p>
<p>More thoughts here with #hashtags.</p>
</article>
</body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.source_platform == "threads"
        assert result.status.value in ("success", "partial")
        assert "@username" in result.title or "@username" in result.metadata.get("author", "")
        # Check for title section
        section_kinds = [s.kind for s in result.sections]
        assert "title" in section_kinds

    @respx.mock
    def test_extract_limited(self):
        """Threads with minimal text → partial with metadata_block."""
        processor = ThreadsProcessor()
        url = "https://threads.net/@anotheruser/post/9876543210"

        # Minimal HTML that trafilatura can't extract much from
        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="Limited Thread">
<meta property="og:description" content="A short preview.">
</head>
<body><p>Sign in to see full thread.</p></body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.source_platform == "threads"
        assert result.metadata.get("limited_extraction") is True
        if result.metadata.get("limited_extraction"):
            assert result.status.value == "partial"
            section_kinds = [s.kind for s in result.sections]
            assert "metadata_block" in section_kinds

    @respx.mock
    def test_extract_fetch_returns_none(self):
        """Threads fetch fails → partial result."""
        processor = ThreadsProcessor()
        url = "https://threads.net/@user/post/123"

        async def side_effect(request):
            raise Exception("Threads blocked")

        respx.get(url).mock(side_effect=side_effect)

        result = asyncio.run(processor.process(url))

        assert result.status.value == "partial"
        assert result.metadata.get("limited_extraction") is True

    @respx.mock
    def test_extract_author_from_url(self):
        """Author extracted from URL path when not in OG metadata."""
        processor = ThreadsProcessor()
        url = "https://threads.net/@techcreator/post/555666777888999"

        html_content = """<!DOCTYPE html>
<html>
<head>
<title>Thread</title>
<meta property="og:description" content="Tech content thread.">
</head>
<body><p>Some content.</p></body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.metadata.get("author") == "techcreator"

    @respx.mock
    def test_extract_returns_result(self):
        """Threads processor returns a valid result."""
        processor = ThreadsProcessor()
        url = "https://threads.net/@user/post/123456789"

        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="Thread Post">
<meta property="og:description" content="A post description.">
</head>
<body><p>Content.</p></body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.source_platform == "threads"
        assert result.status.value in ("success", "partial")

    def test_url_pattern_matching(self):
        """Processor URL regex patterns match expected URLs via match_processor."""
        from fourdpocket.processors.registry import match_processor

        proc = match_processor("https://threads.net/@user/post/123")
        assert type(proc).__name__ == "ThreadsProcessor"

        proc = match_processor("https://www.threads.net/@person/post/111")
        assert type(proc).__name__ == "ThreadsProcessor"
