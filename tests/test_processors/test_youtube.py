"""Tests for YouTube processor extract() and edge cases."""

from __future__ import annotations

import asyncio
import re
import sys
from unittest.mock import MagicMock, patch

import pytest

from fourdpocket.processors.youtube import YouTubeProcessor, _extract_video_id

# ─── URL pattern matching ────────────────────────────────────────────────────


class TestURLPatternMatching:
    """Processor matches expected URL patterns."""

    @pytest.mark.parametrize("url,expected_id", [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=abc123XYZ19", "abc123XYZ19"),
        ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ])
    def test_extracts_video_id_from_various_urls(self, url: str, expected_id: str):
        assert _extract_video_id(url) == expected_id

    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
    ])
    def test_matches_youtube_url_patterns(self, url: str):
        proc = YouTubeProcessor()
        matches = any(re.search(p, url) for p in proc.url_patterns)
        assert matches, f"URL did not match: {url}"

    def test_unknown_url_returns_none(self):
        assert _extract_video_id("https://example.com/video") is None


class TestYouTubeProcessor:
    """Test the YouTubeProcessor.process() method."""

    def test_video_id_extraction_failed(self):
        """URL without video ID → failed status."""
        proc = YouTubeProcessor()
        result = asyncio.run(proc.process("https://www.youtube.com/"))
        assert result.status.value == "failed"
        assert "Could not extract video ID" in result.error

    def test_video_id_extraction_invalid_url(self):
        """Invalid YouTube URL → failed status."""
        proc = YouTubeProcessor()
        result = asyncio.run(proc.process("https://notyoutube.com/watch?v=abc"))
        assert result.status.value == "failed"
        assert "Could not extract video ID" in result.error


# === PHASE 2A MOPUP ADDITIONS ===

def _make_mock_ytdlp(info=None, exc=None):
    """Build a fake yt_dlp module whose YoutubeDL returns a context manager."""
    inst = MagicMock()
    inst.__enter__ = MagicMock(return_value=inst)
    inst.__exit__ = MagicMock(return_value=False)
    inst.extract_info.return_value = info
    if exc:
        inst.extract_info.side_effect = exc
    m = MagicMock()
    m.YoutubeDL.return_value = inst
    return m


def _make_mock_youtube_transcript_api(mock_tlist):
    """Build a fake youtube_transcript_api module with list_transcripts."""
    mock_yta = MagicMock()
    mock_yta.YouTubeTranscriptApi.list_transcripts = MagicMock(
        side_effect=lambda vid: mock_tlist
    )
    mock_module = MagicMock()
    mock_module.YouTubeTranscriptApi = mock_yta.YouTubeTranscriptApi
    return mock_module


class TestYouTubeProcess:
    """Full process() tests with yt-dlp + transcript mocking."""

    def test_process_with_yt_dlp_and_transcript(self):
        """yt-dlp returns metadata + chapters; transcript API returns segments."""
        info = {
            "title": "Test Video",
            "description": "This is a test video description.",
            "thumbnail": "https://img.youtube.com/vi/abc123xAbC1/maxresdefault.jpg",
            "duration": 600,
            "channel": "Test Channel",
            "channel_id": "UC123",
            "channel_url": "https://youtube.com/channel/UC123",
            "view_count": 10000,
            "like_count": 500,
            "upload_date": "20240101",
            "categories": ["Education"],
            "tags": ["python", "tutorial"],
            "chapters": [
                {"title": "Intro", "start_time": 0, "end_time": 120},
                {"title": "Main Content", "start_time": 120, "end_time": 600},
            ],
        }
        mock_transcript = MagicMock()
        mock_transcript.language = "en"
        mock_transcript.is_generated = True
        mock_transcript.fetch.return_value = [
            {"text": "Hello world", "start": 0.0, "duration": 5.0},
            {"text": "This is a test", "start": 5.0, "duration": 5.0},
        ]
        mock_tlist = MagicMock()
        mock_tlist.find_manually_created_transcript.side_effect = Exception("no manual")
        mock_tlist.find_generated_transcript.return_value = mock_transcript
        mock_tlist.__iter__ = MagicMock(return_value=iter([mock_transcript]))

        mock_ytdlp = _make_mock_ytdlp(info)
        mock_yta = _make_mock_youtube_transcript_api(mock_tlist)

        with patch.dict(sys.modules, {
            "yt_dlp": mock_ytdlp,
            "yt_dlp.utils": MagicMock(),
            "yt_dlp.options": MagicMock(),
            "youtube_transcript_api": mock_yta,
        }):
            proc = YouTubeProcessor()
            result = asyncio.run(proc.process("https://www.youtube.com/watch?v=abc123xAbC1"))

        assert result.source_platform == "youtube"
        assert result.status.value == "success"
        assert result.title == "Test Video"
        assert result.metadata["channel"] == "Test Channel"
        assert result.metadata["duration"] == 600
        assert "chapters" in result.metadata
        section_kinds = {s.kind for s in result.sections}
        assert "title" in section_kinds
        assert "chapter" in section_kinds
        assert "transcript_segment" in section_kinds

    def test_process_yt_dlp_not_installed(self):
        """yt-dlp not installed → failed status."""
        with patch.dict(sys.modules, {"yt_dlp": None}):
            proc = YouTubeProcessor()
            result = asyncio.run(proc.process("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        assert result.status.value == "failed"
        assert "not installed" in result.error

    def test_process_yt_dlp_exception(self):
        """yt-dlp raises exception → partial with yt_dlp_error in metadata."""
        mock_ytdlp = _make_mock_ytdlp(exc=RuntimeError("extraction failed"))
        mock_tlist = MagicMock()
        mock_tlist.find_manually_created_transcript.side_effect = Exception("no manual")
        mock_tlist.find_generated_transcript.side_effect = Exception("no transcript")
        mock_tlist.__iter__ = MagicMock(return_value=iter([]))
        mock_yta = _make_mock_youtube_transcript_api(mock_tlist)

        with patch.dict(sys.modules, {
            "yt_dlp": mock_ytdlp,
            "yt_dlp.utils": MagicMock(),
            "yt_dlp.options": MagicMock(),
            "youtube_transcript_api": mock_yta,
        }):
            proc = YouTubeProcessor()
            result = asyncio.run(proc.process("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))

        assert result.status.value == "partial"
        assert "yt_dlp_error" in result.metadata

    def test_process_no_chapters_no_transcript(self):
        """No chapters and no transcript → still success."""
        info = {
            "title": "Simple Video",
            "description": "No chapters here.",
            "duration": 180,
        }
        mock_ytdlp = _make_mock_ytdlp(info)
        mock_tlist = MagicMock()
        mock_tlist.find_manually_created_transcript.side_effect = Exception("no manual")
        mock_tlist.find_generated_transcript.side_effect = Exception("no transcript")
        mock_tlist.__iter__ = MagicMock(return_value=iter([]))
        mock_yta = _make_mock_youtube_transcript_api(mock_tlist)

        with patch.dict(sys.modules, {
            "yt_dlp": mock_ytdlp,
            "yt_dlp.utils": MagicMock(),
            "yt_dlp.options": MagicMock(),
            "youtube_transcript_api": mock_yta,
        }):
            proc = YouTubeProcessor()
            result = asyncio.run(proc.process("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))

        assert result.status.value == "success"
        assert result.title == "Simple Video"

    def test_process_title_missing_downgrades_to_partial(self):
        """yt-dlp returns no title → partial status."""
        info = {"description": "Only a description"}
        mock_ytdlp = _make_mock_ytdlp(info)
        mock_tlist = MagicMock()
        mock_tlist.find_manually_created_transcript.side_effect = Exception("no manual")
        mock_tlist.find_generated_transcript.side_effect = Exception("no transcript")
        mock_tlist.__iter__ = MagicMock(return_value=iter([]))
        mock_yta = _make_mock_youtube_transcript_api(mock_tlist)

        with patch.dict(sys.modules, {
            "yt_dlp": mock_ytdlp,
            "yt_dlp.utils": MagicMock(),
            "yt_dlp.options": MagicMock(),
            "youtube_transcript_api": mock_yta,
        }):
            proc = YouTubeProcessor()
            result = asyncio.run(proc.process("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))

        assert result.status.value == "partial"
        assert "Could not extract full metadata" in result.error


class TestChapterForTimestamp:
    """_chapter_for_timestamp helper."""

    def test_chapter_found(self):
        from fourdpocket.processors.youtube import _chapter_for_timestamp

        chapters = [
            {"start_time": 0, "end_time": 120},
            {"start_time": 120, "end_time": 600},
        ]
        assert _chapter_for_timestamp(chapters, 0) == 0
        assert _chapter_for_timestamp(chapters, 60) == 0
        assert _chapter_for_timestamp(chapters, 120) == 1
        assert _chapter_for_timestamp(chapters, 300) == 1

    def test_chapter_not_found(self):
        from fourdpocket.processors.youtube import _chapter_for_timestamp

        chapters = [{"start_time": 0, "end_time": 120}]
        assert _chapter_for_timestamp(chapters, 999) is None
        assert _chapter_for_timestamp([], 0) is None