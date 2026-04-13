"""Tests for Instagram processor."""
import asyncio

import respx
from httpx import Response

from fourdpocket.processors.instagram import InstagramProcessor, _extract_shortcode


class TestExtract:
    """Test the extract() method with mocked HTTP responses."""

    @respx.mock
    def test_extract_instaloader_failure(self):
        """instaloader fails → OG fallback with limited extraction."""
        processor = InstagramProcessor()
        url = "https://www.instagram.com/p/AbCdEfGhIjK/"

        shortcode = "AbCdEfGhIjK"

        # Simulate instaloader failure (ImportError or runtime error)
        # The processor catches Exception and calls _og_fallback
        async def side_effect(request):
            # First call is the install check (import), second is the actual fetch
            raise Exception("instaloader rate limited")

        # Mock the fallback fetch
        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="Instagram Post">
<meta property="og:description" content="A photo shared on Instagram.">
<meta property="og:image" content="https://example.com/photo.jpg">
</head>
<body></body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        assert result.source_platform == "instagram"
        assert result.status.value == "partial"
        assert result.metadata.get("limited_extraction") is True
        assert result.metadata.get("shortcode") == shortcode
        # Should have metadata_block explaining limitation
        section_kinds = [s.kind for s in result.sections]
        assert "metadata_block" in section_kinds

    @respx.mock
    def test_extract_instaloader_not_installed(self):
        """instaloader not installed → OG fallback."""
        processor = InstagramProcessor()
        url = "https://www.instagram.com/p/HiJkLmNoPqR/"

        shortcode = "HiJkLmNoPqR"

        html_content = """<!DOCTYPE html>
<html>
<head>
<title>Instagram</title>
<meta property="og:title" content="Image Post">
<meta property="og:description" content="Instagram image description.">
<meta property="og:image" content="https://example.com/img.jpg">
</head>
<body></body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        # Patch instaloader import to raise ImportError
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else None

        def mock_import(name, *args, **kwargs):
            if name == 'instaloader':
                raise ImportError("instaloader not installed")
            return original_import(name, *args, **kwargs) if original_import else __import__(name, *args, **kwargs)

        import builtins
        saved_import = builtins.__import__
        builtins.__import__ = mock_import

        try:
            result = asyncio.run(processor.process(url))
        finally:
            builtins.__import__ = saved_import

        assert result.source_platform == "instagram"
        assert result.status.value == "partial"
        assert "instaloader" in result.error or result.metadata.get("fallback") == "og_metadata"

    def test_extract_invalid_shortcode(self):
        """URL without valid shortcode → failed result."""
        processor = InstagramProcessor()
        url = "https://www.instagram.com/"

        result = asyncio.run(processor.process(url))

        assert result.status.value == "failed"
        assert "shortcode" in result.error.lower()

    def test_extract_shortcode_extraction(self):
        """Shortcode extracted from various Instagram URL formats."""
        assert _extract_shortcode("https://www.instagram.com/p/AbCdEfGhIjK/") == "AbCdEfGhIjK"
        assert _extract_shortcode("https://instagram.com/p/HiJkLmNoPqR") == "HiJkLmNoPqR"
        assert _extract_shortcode("https://www.instagram.com/reel/ReEl12345678/") == "ReEl12345678"
        assert _extract_shortcode("https://www.instagram.com/reels/ReEl87654321") == "ReEl87654321"
        assert _extract_shortcode("https://www.instagram.com/username/p/UsErNaMe12345/") == "UsErNaMe12345"
        assert _extract_shortcode("https://twitter.com/user/post") is None

    def test_url_pattern_matching(self):
        """Processor URL regex patterns match expected URLs via match_processor."""
        from fourdpocket.processors.registry import match_processor

        proc = match_processor("https://www.instagram.com/p/AbCd1234/")
        assert type(proc).__name__ == "InstagramProcessor"

        proc = match_processor("https://www.instagram.com/reel/AbCd1234/")
        assert type(proc).__name__ == "InstagramProcessor"

    @respx.mock
    def test_extract_fetch_fallback_error(self):
        """Both instaloader and OG fallback fail → partial."""
        processor = InstagramProcessor()
        url = "https://www.instagram.com/p/TeSt12345678/"

        async def side_effect(request):
            raise Exception("Network error")

        respx.get(url).mock(side_effect=side_effect)

        result = asyncio.run(processor.process(url))

        assert result.status.value == "partial"
        assert result.metadata.get("limited_extraction") is True


# === PHASE 2A MOPUP ADDITIONS ===
from unittest.mock import MagicMock, patch


class TestInstagramProcess:
    """Full process() tests with instaloader mocking."""

    @patch.dict("sys.modules", {"instaloader": MagicMock()})
    def test_process_with_instaloader_success(self, monkeypatch, respx_mock):
        """instaloader returns post → success with sections."""

        # Build a realistic mock post
        mock_post = MagicMock()
        mock_post.typename = "GraphImage"
        mock_post.caption = "Beautiful sunset! #photography #nature"
        mock_post.owner_username = "test_user"
        mock_post.date = MagicMock()
        mock_post.date.isoformat.return_value = "2024-01-15T12:00:00"
        mock_post.likes = 1234
        mock_post.comments = 56
        mock_post.is_video = False
        mock_post.url = "https://example.com/image.jpg"
        mock_post.accessibility_caption = "A beautiful sunset over the ocean"

        # Make Post.from_shortcode return our mock
        monkeypatch.setattr(
            "instaloader.Post.from_shortcode",
            MagicMock(return_value=mock_post),
        )

        url = "https://www.instagram.com/p/AbCdEfGhIjK/"
        respx_mock.get(url).mock(
            return_value=Response(200, text="<html></html>")
        )

        proc = InstagramProcessor()
        result = asyncio.run(proc.process(url))

        assert result.source_platform == "instagram"
        assert result.status.value == "success"
        assert result.title.startswith("@test_user")
        assert result.metadata["owner"] == "test_user"
        assert result.metadata["likes"] == 1234
        section_kinds = {s.kind for s in result.sections}
        assert "post" in section_kinds
        assert "visual_caption" in section_kinds

    @patch.dict("sys.modules", {"instaloader": MagicMock()})
    def test_process_reel(self, monkeypatch, respx_mock):
        """Reel detected via URL → is_reel=True in metadata."""

        mock_post = MagicMock()
        mock_post.typename = "GraphVideo"
        mock_post.caption = "Funny reel #funny"
        mock_post.owner_username = "reel_user"
        mock_post.date = MagicMock()
        mock_post.date.isoformat.return_value = "2024-02-01T10:00:00"
        mock_post.likes = 999
        mock_post.comments = 42
        mock_post.is_video = True
        mock_post.video_url = "https://example.com/video.mp4"
        mock_post.url = "https://example.com/thumb.jpg"

        monkeypatch.setattr(
            "instaloader.Post.from_shortcode",
            MagicMock(return_value=mock_post),
        )

        url = "https://www.instagram.com/reel/ReEl12345678/"
        respx_mock.get(url).mock(
            return_value=Response(200, text="<html></html>")
        )

        proc = InstagramProcessor()
        result = asyncio.run(proc.process(url))

        assert result.metadata["is_reel"] is True
        assert result.metadata["is_video"] is True

    @patch.dict("sys.modules", {"instaloader": MagicMock()})
    def test_process_instaloader_exception_falls_back_to_og(self, monkeypatch, respx_mock):
        """instaloader raises exception → OG fallback."""

        monkeypatch.setattr(
            "instaloader.Post.from_shortcode",
            MagicMock(side_effect=RuntimeError("rate limited")),
        )

        url = "https://www.instagram.com/p/AbCdEfGhIjK/"
        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="Instagram Post">
<meta property="og:description" content="A great post.">
<meta property="og:image" content="https://example.com/img.jpg">
</head>
<body></body>
</html>"""
        respx_mock.get(url).mock(return_value=Response(200, text=html_content))

        proc = InstagramProcessor()
        result = asyncio.run(proc.process(url))

        assert result.status.value == "partial"
        assert result.metadata.get("limited_extraction") is True
        assert result.metadata.get("fallback") == "og_metadata"

    def test_process_invalid_shortcode_url(self):
        """URL without shortcode pattern → failed."""
        proc = InstagramProcessor()
        result = asyncio.run(proc.process("https://www.instagram.com/"))
        assert result.status.value == "failed"
        assert "shortcode" in result.error.lower()
