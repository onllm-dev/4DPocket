"""Tests for Spotify oEmbed processor."""
import asyncio

import respx
from httpx import Response

from fourdpocket.processors.spotify import SpotifyProcessor


class TestExtract:
    """Test the extract() method with mocked HTTP responses."""

    @respx.mock
    def test_extract_track(self):
        """Spotify track → oEmbed metadata."""
        processor = SpotifyProcessor()
        url = "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC"

        oembed_response = {
            "title": "Mr. Brightside",
            "author_name": "The Killers",
            "thumbnail_url": "https://i.scdn.co/image/ab67616d0000b2738863bc11d2aa12b54f5aeb36",
            "provider_name": "Spotify",
            "html": '<iframe src="https://open.spotify.com/embed/track/..."></iframe>',
        }

        respx.get(
            url__regex=r"https://open\.spotify\.com/oembed\?url=https://open\.spotify\.com/track/"
        ).mock(return_value=Response(200, json=oembed_response))

        result = asyncio.run(processor.process(url))

        assert result.status.value == "success"
        assert result.source_platform == "spotify"
        assert "Mr. Brightside" in result.title
        assert "Killers" in result.description
        assert result.metadata["author"] == "The Killers"
        assert result.metadata["spotify_type"] == "track"
        assert result.metadata["provider"] == "Spotify"
        assert len(result.media) == 1
        assert result.media[0]["type"] == "image"
        assert result.media[0]["role"] == "thumbnail"

    @respx.mock
    def test_extract_album(self):
        """Spotify album → oEmbed metadata."""
        processor = SpotifyProcessor()
        url = "https://open.spotify.com/album/1DFixLW3zckG3rN9xY1kSj"

        oembed_response = {
            "title": "Hot Fuss",
            "author_name": "The Killers",
            "thumbnail_url": "https://i.scdn.co/image/ab67616d0000b27350a3147b4c3a1d8a70d6cec8",
            "provider_name": "Spotify",
            "html": '<iframe src="https://open.spotify.com/embed/album/..."></iframe>',
        }

        respx.get(
            url__regex=r"https://open\.spotify\.com/oembed\?url=https://open\.spotify\.com/album/"
        ).mock(return_value=Response(200, json=oembed_response))

        result = asyncio.run(processor.process(url))

        assert result.status.value == "success"
        assert "Hot Fuss" in result.title
        assert result.metadata["spotify_type"] == "album"

    @respx.mock
    def test_extract_playlist(self):
        """Spotify playlist → oEmbed metadata."""
        processor = SpotifyProcessor()
        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

        oembed_response = {
            "title": "Today's Top Hits",
            "author_name": "Spotify",
            "thumbnail_url": "https://i.scdn.co/image/ab67616d0000b273...",
            "provider_name": "Spotify",
            "html": '<iframe src="https://open.spotify.com/embed/playlist/..."></iframe>',
        }

        respx.get(
            url__regex=r"https://open\.spotify\.com/oembed\?url=https://open\.spotify\.com/playlist/"
        ).mock(return_value=Response(200, json=oembed_response))

        result = asyncio.run(processor.process(url))

        assert result.status.value == "success"
        assert "Top Hits" in result.title
        assert result.metadata["spotify_type"] == "playlist"

    @respx.mock
    def test_extract_http_error(self):
        """HTTP error from oEmbed → partial result."""
        processor = SpotifyProcessor()
        url = "https://open.spotify.com/track/1234567890"

        respx.get(url__regex=r"https://open\.spotify\.com/oembed").mock(
            return_value=Response(404)
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "partial"
        assert "404" in result.error

    @respx.mock
    def test_extract_network_error(self):
        """Network error → failed result."""
        processor = SpotifyProcessor()
        url = "https://open.spotify.com/track/ABCD1234"

        respx.get(url__regex=r"https://open\.spotify\.com/oembed").mock(
            side_effect=Exception("Connection refused")
        )

        result = asyncio.run(processor.process(url))

        assert result.status.value == "failed"

    def test_url_pattern_matching(self):
        """Processor URL regex patterns match expected URLs via match_processor."""
        from fourdpocket.processors.registry import match_processor

        proc = match_processor("https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC")
        assert type(proc).__name__ == "SpotifyProcessor"

        proc = match_processor("https://open.spotify.com/album/1DFixLW3zckG3rN9xY1kSj")
        assert type(proc).__name__ == "SpotifyProcessor"
