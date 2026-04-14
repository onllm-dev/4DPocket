"""Tests for LinkedIn processor."""
import asyncio

import respx
from httpx import Response

from fourdpocket.processors.linkedin import LinkedInProcessor


class TestExtract:
    """Test the extract() method with mocked HTTP responses."""

    @respx.mock
    def test_extract_pulse_article(self):
        """LinkedIn Pulse article → partial (limited extraction)."""
        processor = LinkedInProcessor()
        url = "https://linkedin.com/pulse/how-to-become-better-programmer-john-doe"

        html_content = """<!DOCTYPE html>
<html>
<head>
<title>How to become a better programmer - John Doe</title>
<meta property="og:title" content="How to become a better programmer">
<meta property="og:description" content="A guide to improving your coding skills.">
<meta property="og:image" content="https://example.com/cover.jpg">
<meta property="og:site_name" content="LinkedIn">
<meta name="author" content="John Doe">
</head>
<body>
<article>
<p>Programming is a craft that requires continuous learning...</p>
<p>Here are some tips for becoming better:</p>
</article>
</body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.source_platform == "linkedin"
        assert result.status.value in ("success", "partial")
        assert "programmer" in result.title.lower()
        assert result.metadata["author"] == "John Doe"
        assert result.metadata["post_type"] == "article"
        # Pulse articles should have more content
        if result.metadata.get("limited_extraction"):
            assert result.status.value == "partial"

    @respx.mock
    def test_extract_post(self):
        """LinkedIn post URL → partial due to auth wall."""
        processor = LinkedInProcessor()
        url = "https://linkedin.com/posts/user123/interesting-thoughts"

        html_content = """<!DOCTYPE html>
<html>
<head>
<title>User Post</title>
<meta property="og:title" content="LinkedIn Post">
<meta property="og:description" content="A short preview.">
</head>
<body>
<p>Limited preview content.</p>
</body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.source_platform == "linkedin"
        # Posts behind auth wall typically get limited extraction
        assert result.metadata.get("limited_extraction") is True

    @respx.mock
    def test_extract_fetch_returns_none(self):
        """LinkedIn blocks fetch → partial result."""
        processor = LinkedInProcessor()
        url = "https://linkedin.com/posts/test"

        # Simulate fetch returning None due to blocking
        async def side_effect(request):
            raise Exception("LinkedIn blocked")

        respx.get(url).mock(side_effect=side_effect)

        result = asyncio.run(processor.process(url))

        assert result.status.value == "partial"
        assert result.error is not None
        assert result.metadata.get("limited_extraction") is True

    @respx.mock
    def test_extract_http_401(self):
        """LinkedIn returns 401 → partial with error."""
        processor = LinkedInProcessor()
        url = "https://linkedin.com/posts/user/private"

        respx.get(url).mock(return_value=Response(401))

        result = asyncio.run(processor.process(url))

        assert result.status.value == "partial"
        assert result.metadata.get("limited_extraction") is True

    @respx.mock
    def test_extract_og_metadata(self):
        """OG metadata used when body extraction is minimal."""
        processor = LinkedInProcessor()
        url = "https://linkedin.com/posts/user/post-123"

        # Minimal HTML that trafilatura can't extract much from
        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="Shared Article Title">
<meta property="og:description" content="A great article about tech.">
<meta property="og:image" content="https://example.com/article.jpg">
<meta property="og:site_name" content="LinkedIn">
</head>
<body><p>Sign in to see more.</p></body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.source_platform == "linkedin"
        assert result.metadata.get("limited_extraction") is True
        # OG description used as fallback body
        assert result.description is not None
        assert result.sections[-1].kind == "metadata_block"

    def test_url_pattern_matching(self):
        """Processor URL regex patterns match expected URLs via match_processor."""
        from fourdpocket.processors.registry import match_processor

        proc = match_processor("https://linkedin.com/posts/user123/abc")
        assert type(proc).__name__ == "LinkedInProcessor"

        proc = match_processor("https://linkedin.com/pulse/article-title-author")
        assert type(proc).__name__ == "LinkedInProcessor"
