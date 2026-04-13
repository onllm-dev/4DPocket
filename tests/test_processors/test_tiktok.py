"""Tests for TikTok processor."""
import asyncio
import sys
from unittest.mock import MagicMock

import respx
from httpx import Response

from fourdpocket.processors.tiktok import TikTokProcessor, _split_caption


class TestExtract:
    """Test the extract() method."""

    def test_split_caption(self):
        """Caption split into body and hashtags."""
        body, hashtags = _split_caption("Check out this trick! #fyp #viral")
        assert body == "Check out this trick!"
        assert hashtags == ["fyp", "viral"]

        body2, tags2 = _split_caption("No hashtags here")
        assert body2 == "No hashtags here"
        assert tags2 == []

        body3, tags3 = _split_caption("#only #hashtags")
        assert body3 == ""
        assert tags3 == ["only", "hashtags"]

    def test_url_pattern_matching(self):
        """Processor URL regex patterns match expected URLs via match_processor."""
        from fourdpocket.processors.registry import match_processor

        proc = match_processor("https://www.tiktok.com/@user/video/1234567890")
        assert type(proc).__name__ == "TikTokProcessor"

        proc = match_processor("https://vm.tiktok.com/AbCdEf/")
        assert type(proc).__name__ == "TikTokProcessor"

        proc = match_processor("https://tiktok.com/t/abc123DEF/")
        assert type(proc).__name__ == "TikTokProcessor"

    @respx.mock
    def test_extract_og_fallback(self):
        """TikTok URL when yt-dlp unavailable → partial with OG metadata."""
        processor = TikTokProcessor()
        url = "https://www.tiktok.com/@user/video/1234567890"

        # OG metadata fallback when yt-dlp would fail
        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="TikTok Video">
<meta property="og:description" content="Watch this video on TikTok.">
<meta property="og:image" content="https://example.com/video-thumb.jpg">
</head>
<body></body>
</html>"""

        respx.get(url).mock(return_value=Response(200, text=html_content))

        result = asyncio.run(processor.process(url))

        # When yt-dlp fails (not installed or error), OG fallback is used
        assert result.source_platform == "tiktok"
        assert result.status.value in ("success", "partial")
        # Should have title section
        section_kinds = [s.kind for s in result.sections]
        assert "title" in section_kinds


# === PHASE 2A MOPUP ADDITIONS ===


class TestTikTokProcess:
    """Full process() tests with yt-dlp mocking."""

    def test_process_with_yt_dlp_success(self, monkeypatch):
        """yt-dlp returns metadata → success with sections."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.extract_info.return_value = {
            "title": "Amazing Trick",
            "description": "Check this out! #fyp #viral #tiktok",
            "uploader": "test_user",
            "thumbnail": "https://example.com/thumb.jpg",
            "like_count": 1000,
            "view_count": 50000,
            "duration": 30,
            "upload_date": "20240101",
        }
        monkeypatch.setattr("yt_dlp.YoutubeDL", MagicMock(return_value=mock_instance))

        proc = TikTokProcessor()
        result = asyncio.run(proc.process("https://www.tiktok.com/@user/video/1234567890"))

        assert result.source_platform == "tiktok"
        assert result.status.value == "success"
        assert result.title == "Amazing Trick"
        assert result.metadata["author"] == "test_user"
        section_kinds = {s.kind for s in result.sections}
        assert "title" in section_kinds
        assert "post" in section_kinds

    def test_process_with_subtitles(self, monkeypatch):
        """yt-dlp returns subtitles → transcript_segment section emitted."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.extract_info.return_value = {
            "title": "Video with subtitles",
            "description": "Subtitled video #tiktok",
            "subtitles": {
                "en": [{"url": "https://example.com/en.vtt"}],
            },
        }
        monkeypatch.setattr("yt_dlp.YoutubeDL", MagicMock(return_value=mock_instance))

        proc = TikTokProcessor()
        result = asyncio.run(proc.process("https://www.tiktok.com/@user/video/1234567890"))

        section_kinds = {s.kind for s in result.sections}
        assert "transcript_segment" in section_kinds

    def test_process_yt_dlp_not_installed(self, monkeypatch):
        """yt-dlp not installed → failed."""
        # Setting sys.modules["yt_dlp"] = None causes ModuleNotFoundError on import
        monkeypatch.setitem(sys.modules, "yt_dlp", None)
        proc = TikTokProcessor()
        result = asyncio.run(proc.process("https://www.tiktok.com/@user/video/1234567890"))
        assert result.status.value == "failed"
        assert "not installed" in result.error

    def test_process_yt_dlp_returns_no_info_og_fallback(self, monkeypatch, respx_mock):
        """yt-dlp returns None → OG fallback."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.extract_info.return_value = None
        monkeypatch.setattr("yt_dlp.YoutubeDL", MagicMock(return_value=mock_instance))

        url = "https://www.tiktok.com/@user/video/1234567890"
        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="TikTok Video">
<meta property="og:description" content="Watch this.">
<meta property="og:image" content="https://example.com/thumb.jpg">
</head>
<body></body>
</html>"""
        respx_mock.get(url).mock(return_value=Response(200, text=html_content))

        proc = TikTokProcessor()
        result = asyncio.run(proc.process(url))

        assert result.status.value == "partial"
        assert result.metadata.get("limited_extraction") is True

    def test_process_yt_dlp_exception_og_fallback(self, monkeypatch, respx_mock):
        """yt-dlp raises exception → OG fallback."""
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.extract_info.side_effect = RuntimeError("network error")
        monkeypatch.setattr("yt_dlp.YoutubeDL", MagicMock(return_value=mock_instance))

        url = "https://www.tiktok.com/@user/video/1234567890"
        html_content = """<!DOCTYPE html>
<html>
<head>
<meta property="og:title" content="TikTok Video">
<meta property="og:description" content="Watch this.">
<meta property="og:image" content="https://example.com/thumb.jpg">
</head>
<body></body>
</html>"""
        respx_mock.get(url).mock(return_value=Response(200, text=html_content))

        proc = TikTokProcessor()
        result = asyncio.run(proc.process(url))

        assert result.status.value == "partial"
        assert "yt-dlp failed" in result.error
