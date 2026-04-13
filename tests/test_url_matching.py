"""Test that URL pattern matching routes every seed URL to the correct processor.

This catches regressions in processor url_patterns — the most common
source of items silently falling through to GenericURLProcessor.
"""

from __future__ import annotations

import pytest

# Force all processors to register
import fourdpocket.processors  # noqa: F401
from fourdpocket.processors.registry import match_processor
from tests.seed_urls import GENERIC_URLS, SEED_URLS

# Map platform key → expected processor class name
_EXPECTED_PROCESSOR = {
    "youtube": "YouTubeProcessor",
    "instagram": "InstagramProcessor",
    "reddit": "RedditProcessor",
    "twitter": "TwitterProcessor",
    "github": "GitHubProcessor",
    "hackernews": "HackerNewsProcessor",
    "stackoverflow": "StackOverflowProcessor",
    "substack": "SubstackProcessor",
    "medium": "MediumProcessor",
    "linkedin": "LinkedInProcessor",
    "mastodon": "MastodonProcessor",
    "tiktok": "TikTokProcessor",
    "threads": "ThreadsProcessor",
    "spotify": "SpotifyProcessor",
}


def _all_platform_urls():
    """Yield (url, expected_class_name) for parametrize."""
    for platform, urls in SEED_URLS.items():
        expected = _EXPECTED_PROCESSOR[platform]
        for url in urls:
            yield pytest.param(url, expected, id=f"{platform}:{url.split('/')[-1][:30]}")


@pytest.mark.parametrize("url,expected_cls", list(_all_platform_urls()))
def test_url_routes_to_correct_processor(url: str, expected_cls: str):
    proc = match_processor(url)
    actual = type(proc).__name__
    assert actual == expected_cls, (
        f"URL {url!r} routed to {actual}, expected {expected_cls}"
    )


@pytest.mark.parametrize("url", GENERIC_URLS)
def test_generic_urls_fall_to_generic(url: str):
    proc = match_processor(url)
    actual = type(proc).__name__
    assert actual == "GenericURLProcessor", (
        f"URL {url!r} should fall to GenericURLProcessor but got {actual}"
    )
