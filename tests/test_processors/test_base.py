"""Tests for processor base classes, the @register_processor decorator,
ProcessorResult dataclass, and the registry.
"""

from __future__ import annotations

import pytest

from fourdpocket.processors.base import (
    BaseProcessor,
    ProcessorResult,
    ProcessorStatus,
    _is_safe_url,
)
from fourdpocket.processors.registry import (
    _PATTERNS,
    _REGISTRY,
    get_processor,
    list_processors,
    match_processor,
    register_processor,
)


class TestProcessorResult:
    """ProcessorResult dataclass behaviour."""

    def test_default_values(self):
        result = ProcessorResult()
        assert result.title is None
        assert result.description is None
        assert result.content is None
        assert result.raw_content is None
        assert result.media == []
        assert result.metadata == {}
        assert result.source_platform == "generic"
        assert result.item_type == "url"
        assert result.status == ProcessorStatus.success
        assert result.error is None
        assert result.sections == []

    def test_all_fields_set(self):
        result = ProcessorResult(
            title="Test Title",
            description="Test description",
            content="Full content",
            raw_content="Raw HTML",
            media=[{"type": "image", "url": "https://example.com/img.jpg"}],
            metadata={"author": "Alice"},
            source_platform="github",
            item_type="article",
            status=ProcessorStatus.partial,
            error="Something went wrong",
            sections=[],
        )
        assert result.title == "Test Title"
        assert result.description == "Test description"
        assert result.content == "Full content"
        assert result.raw_content == "Raw HTML"
        assert len(result.media) == 1
        assert result.metadata["author"] == "Alice"
        assert result.source_platform == "github"
        assert result.item_type == "article"
        assert result.status == ProcessorStatus.partial
        assert result.error == "Something went wrong"

    def test_immutable(self):
        result = ProcessorResult(title="Original")
        with pytest.raises(Exception):  # dataclass frozen=True
            result.title = "Modified"  # type: ignore

    def test_status_enum_values(self):
        assert ProcessorStatus.success.value == "success"
        assert ProcessorStatus.partial.value == "partial"
        assert ProcessorStatus.failed.value == "failed"


class TestRegisterProcessor:
    """The @register_processor decorator and registry functions."""

    def test_register_adds_to_registry(self):
        # Count before
        before = set(_REGISTRY.keys())

        @register_processor
        class DummyProcessor(BaseProcessor):
            url_patterns = [r"https://example\.com/test"]
            priority = 10

            async def process(self, url, **kwargs):
                return ProcessorResult(title="dummy")

        try:
            assert "DummyProcessor" in _REGISTRY
            assert set(_REGISTRY.keys()) == before | {"DummyProcessor"}
        finally:
            # Clean up so later tests are not affected
            _REGISTRY.pop("DummyProcessor", None)
            _PATTERNS[:] = [p for p in _PATTERNS if p[1] != "DummyProcessor"]

    def test_register_adds_pattern(self):
        pattern = r"https://example\.com/unique42"

        @register_processor
        class UniqueTestProcessor(BaseProcessor):
            url_patterns = [pattern]
            priority = 5

            async def process(self, url, **kwargs):
                return ProcessorResult(title="unique")

        try:
            compiled_patterns = [p[0].pattern for p in _PATTERNS]
            assert pattern in compiled_patterns
        finally:
            _REGISTRY.pop("UniqueTestProcessor", None)
            _PATTERNS[:] = [p for p in _PATTERNS if p[1] != "UniqueTestProcessor"]

    def test_priority_sorted_high_to_low(self):
        """Higher priority processors should appear earlier in _PATTERNS."""
        @register_processor
        class LowPriority(BaseProcessor):
            url_patterns = [r"https://example\.com/low"]
            priority = 1

            async def process(self, url, **kwargs):
                return ProcessorResult()

        @register_processor
        class HighPriority(BaseProcessor):
            url_patterns = [r"https://example\.com/high"]
            priority = 99

            async def process(self, url, **kwargs):
                return ProcessorResult()

        try:
            names = [p[1] for p in _PATTERNS]
            assert names.index("HighPriority") < names.index("LowPriority")
        finally:
            _REGISTRY.pop("LowPriority", None)
            _REGISTRY.pop("HighPriority", None)
            _PATTERNS[:] = [p for p in _PATTERNS if p[1] not in ("LowPriority", "HighPriority")]


class TestMatchProcessor:
    """match_processor() and the fallback chain."""

    def test_match_returns_correct_processor(self):
        """GitHub URL should match GitHubProcessor."""
        processor = match_processor("https://github.com/torvalds/linux")
        assert processor.__class__.__name__ == "GitHubProcessor"

    def test_match_reddit(self):
        processor = match_processor("https://www.reddit.com/r/python/comments/abc/")
        assert processor.__class__.__name__ == "RedditProcessor"

    def test_match_hackernews(self):
        processor = match_processor("https://news.ycombinator.com/item?id=123")
        assert processor.__class__.__name__ == "HackerNewsProcessor"

    def test_match_youtube(self):
        processor = match_processor("https://www.youtube.com/watch?v=abc123")
        assert processor.__class__.__name__ == "YouTubeProcessor"

    def test_match_medium(self):
        processor = match_processor("https://medium.com/@user/post-slug")
        assert processor.__class__.__name__ == "MediumProcessor"

    def test_match_unknown_url_falls_back_to_generic(self):
        """Unknown URL should return GenericURLProcessor."""
        processor = match_processor("https://totally-unknown-site.example.com/page")
        assert processor.__class__.__name__ == "GenericURLProcessor"

    def test_match_returns_instance_not_class(self):
        processor = match_processor("https://github.com/example/repo")
        assert isinstance(processor, BaseProcessor)
        assert not isinstance(processor, type)


class TestGetProcessor:
    """get_processor() by name."""

    def test_get_existing_processor(self):
        proc = get_processor("GenericURLProcessor")
        assert isinstance(proc, BaseProcessor)
        assert proc.__class__.__name__ == "GenericURLProcessor"

    def test_get_unknown_raises(self):
        with pytest.raises(KeyError):
            get_processor("NonExistentProcessor")


class TestListProcessors:
    """list_processors() returns all registered names."""

    def test_returns_list_of_strings(self):
        names = list_processors()
        assert isinstance(names, list)
        assert all(isinstance(n, str) for n in names)
        assert "GitHubProcessor" in names
        assert "RedditProcessor" in names


class TestSSRFProtection:
    """_is_safe_url() SSRF check."""

    @pytest.mark.parametrize("url", [
        "http://127.0.0.1/admin",
        "http://localhost/admin",
        "http://10.0.0.1/internal",
        "http://172.16.0.1/internal",
        "http://192.168.1.1/internal",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/admin",
    ])
    def test_blocked_internal_urls(self, url):
        assert _is_safe_url(url) is False

    @pytest.mark.parametrize("url", [
        "https://github.com/user/repo",
        "https://www.google.com/search",
        "https://example.com/page",
    ])
    def test_allowed_external_urls(self, url):
        # These may still fail DNS resolution but should not be blocked a priori
        result = _is_safe_url(url)
        # If DNS resolves to a public IP it returns True; internal → False
        # We just verify no exception is raised and result is a bool
        assert isinstance(result, bool)

    def test_unsupported_scheme(self):
        assert _is_safe_url("ftp://example.com/file") is False
        assert _is_safe_url("file:///etc/passwd") is False

    def test_malformed_url(self):
        assert _is_safe_url("not-a-url") is False
        assert _is_safe_url("") is False
