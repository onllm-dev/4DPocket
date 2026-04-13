"""Tests for Medium processor extract() and edge cases."""

from __future__ import annotations

import asyncio
import json
import re
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from fourdpocket.processors.medium import (
    MediumProcessor,
    _extract_post_id,
    _extract_publication,
    _sections_from_medium_payload,
)

# ─── URL pattern matching ────────────────────────────────────────────────────


class TestURLPatternMatching:
    """Processor matches expected URL patterns."""

    @pytest.mark.parametrize("url", [
        "https://medium.com/@user/some-article-title-abc123",
        "https://pythonprogramming.medium.com/some-article-xyz",
        "https://blog.medium.com/some-post",
    ])
    def test_matches_medium_url_patterns(self, url: str):
        proc = MediumProcessor()
        matches = any(re.search(p, url) for p in proc.url_patterns)
        assert matches, f"URL did not match: {url}"

    def test_publication_subdomain_extraction(self):
        """Publication name extracted from subdomain."""
        assert _extract_publication("https://pythonprogramming.medium.com/foo", {}) == "pythonprogramming"
        assert _extract_publication("https://blog.medium.com/bar", {}) == "blog"

    def test_post_id_extraction(self):
        """Post hex ID extracted from URL."""
        url = "https://medium.com/@user/why-python-rocks-abc123def"
        assert _extract_post_id(url) == "abc123def"


MEDIUM_PAYLOAD = {
    "value": {
        "title": "Why Python Is Great",
        "creatorId": "u1",
        "content": {
            "subtitle": "A short subtitle.",
            "bodyModel": {
                "paragraphs": [
                    {"type": 3, "text": "Background Section"},
                    {"type": 1, "text": "Python has simple syntax."},
                    {"type": 6, "text": "Simple is better than complex."},
                    {"type": 8, "text": "print('hello')"},
                ],
            },
        },
        "virtuals": {
            "totalClapCount": 500,
            "readingTime": 3.5,
            "wordCount": 600,
            "tags": [{"slug": "python"}, {"slug": "programming"}],
            "previewImage": {"imageId": "abc.jpg"},
        },
        "firstPublishedAt": 1700000000,
    },
    "references": {
        "User": {
            "u1": {"name": "Python Author"},
        },
    },
}


class TestExtract:
    """Test the MediumProcessor.process() method."""

    @respx.mock(assert_all_called=False)
    def test_extract_via_json_endpoint_success(self):
        """Medium JSON endpoint returns typed sections via respx mock."""
        proc = MediumProcessor()

        # Patch _try_internal_api to return None so we skip curl_cffi path
        with patch("fourdpocket.processors.medium._try_internal_api", return_value=None):
            with respx.mock(assert_all_called=False) as r:
                prefix = "])}while(1);</x>"
                body = prefix + json.dumps({"payload": MEDIUM_PAYLOAD})
                r.get(url__regex=r"https://medium\.com/@user/why-python.*\?format=json").mock(
                    return_value=httpx.Response(200, text=body)
                )
                result = asyncio.run(
                    proc.process("https://medium.com/@user/why-python-rocks-abc123def")
                )

        assert result.source_platform == "medium"
        assert result.status.value == "success"
        assert result.title == "Why Python Is Great"

    @respx.mock(assert_all_called=False)
    def test_extract_json_endpoint_404_falls_back_to_html(self):
        """JSON endpoint 404 falls back to HTML path with OG metadata."""
        proc = MediumProcessor()

        def side_effect(url, **kwargs):
            if "format=json" in url:
                return httpx.Response(404)
            raise httpx.ConnectError("no JSON")

        with patch("fourdpocket.processors.medium._try_internal_api", return_value=None):
            with respx.mock(assert_all_called=False) as r:
                r.get(url__regex=r"https://medium\.com/@user/notfound.*").mock(
                    side_effect=side_effect
                )
                r.get(url__regex=r"https://medium\.com/@user/notfound.*").mock(
                    return_value=httpx.Response(200, text="<html><head><meta property='og:title' content='Article'/><meta property='og:description' content='Missing'/></head></html>")
                )
                result = asyncio.run(
                    proc.process("https://medium.com/@user/notfound-abc123")
                )

        assert result.source_platform == "medium"

    @respx.mock(assert_all_called=False)
    def test_extract_network_error_on_both_paths(self):
        """Network error on both paths → graceful failure."""
        proc = MediumProcessor()

        def side_effect(url, **kwargs):
            raise httpx.ConnectError("connection refused")

        with patch("fourdpocket.processors.medium._try_internal_api", return_value=None):
            with respx.mock(assert_all_called=False) as r:
                r.get(url__regex=r"https://medium\.com/@user/test.*").mock(
                    side_effect=side_effect
                )
                result = asyncio.run(
                    proc.process("https://medium.com/@user/test-abc123")
                )

        assert result.source_platform == "medium"
        assert result.status.value in ("failed", "partial")

    def test_url_pattern_matching(self):
        """Processor correctly matches Medium URL patterns."""
        proc = MediumProcessor()
        url = "https://medium.com/@user/some-article-abc123def"
        matched = any(re.search(p, url) for p in proc.url_patterns)
        assert matched

    @respx.mock(assert_all_called=False)
    def test_extract_metadata(self):
        """Platform-specific metadata extracted correctly."""
        proc = MediumProcessor()

        with patch("fourdpocket.processors.medium._try_internal_api", return_value=None):
            with respx.mock(assert_all_called=False) as r:
                prefix = "])}while(1);</x>"
                body = prefix + json.dumps({"payload": MEDIUM_PAYLOAD})
                r.get(url__regex=r"https://medium\.com/@user/why-python.*\?format=json").mock(
                    return_value=httpx.Response(200, text=body)
                )
                result = asyncio.run(
                    proc.process("https://medium.com/@user/why-python-rocks-abc123def")
                )

        assert result.metadata.get("author") == "Python Author"
        assert result.metadata.get("clap_count") == 500
        assert result.metadata.get("reading_time_min") == 3.5
        assert result.metadata.get("word_count") == 600
        assert "python" in result.metadata.get("tags", [])
        assert "programming" in result.metadata.get("tags", [])

    @respx.mock(assert_all_called=False)
    def test_sections_structure(self):
        """Extracted sections have correct kind, depth, author fields."""
        proc = MediumProcessor()

        with patch("fourdpocket.processors.medium._try_internal_api", return_value=None):
            with respx.mock(assert_all_called=False) as r:
                prefix = "])}while(1);</x>"
                body = prefix + json.dumps({"payload": MEDIUM_PAYLOAD})
                r.get(url__regex=r"https://medium\.com/@user/why-python.*\?format=json").mock(
                    return_value=httpx.Response(200, text=body)
                )
                result = asyncio.run(
                    proc.process("https://medium.com/@user/why-python-rocks-abc123def")
                )

        sections = result.sections
        assert len(sections) >= 4

        title_sections = [s for s in sections if s.kind == "title"]
        assert len(title_sections) == 1
        assert title_sections[0].text == "Why Python Is Great"
        assert title_sections[0].role == "main"

        headings = [s for s in sections if s.kind == "heading"]
        assert any(h.text == "Background Section" for h in headings)

        paragraphs = [s for s in sections if s.kind == "paragraph"]
        assert any("Python has simple syntax" in p.text for p in paragraphs)

        quotes = [s for s in sections if s.kind == "quote"]
        assert len(quotes) == 1
        assert quotes[0].text == "Simple is better than complex."

        code_sections = [s for s in sections if s.kind == "code"]
        assert len(code_sections) == 1
        assert "print" in code_sections[0].text


class TestMediumHelpers:
    """Test helper functions."""

    def test_sections_from_medium_payload(self):
        """_sections_from_medium_payload correctly maps paragraph types."""
        payload = {"payload": MEDIUM_PAYLOAD}
        sections, metadata = _sections_from_medium_payload(
            payload["payload"], "https://medium.com/test"
        )

        assert len(sections) >= 4
        title = next((s for s in sections if s.kind == "title"), None)
        assert title is not None
        assert title.text == "Why Python Is Great"

        assert metadata.get("author") == "Python Author"
        assert metadata.get("clap_count") == 500

    def test_sections_from_empty_payload(self):
        """Empty payload returns empty sections."""
        sections, metadata = _sections_from_medium_payload({"value": {}}, "https://medium.com/test")
        assert sections == []
        assert metadata == {}

    def test_publication_from_og_meta(self):
        """Publication name extracted from og:site_name."""
        og_meta = {"og_site_name": "Tech Blog"}
        assert _extract_publication("https://example.medium.com/foo", og_meta) == "Tech Blog"

    def test_publication_from_subdomain(self):
        """Publication name extracted from subdomain when og_site_name absent."""
        og_meta = {}
        assert _extract_publication("https://pythonprogramming.medium.com/foo", og_meta) == "pythonprogramming"


# === PHASE 2A MOPUP ADDITIONS ===
from fourdpocket.processors.medium import _try_internal_api


class TestMediumHTMLFallback:
    """HTML fallback path when JSON endpoints fail."""

    @respx.mock(assert_all_called=False)
    def test_html_fallback_success(self, respx_mock):
        """HTML path with OG metadata → success."""

        url = "https://medium.com/@user/test-article-abc123"

        # Mock the JSON endpoints to fail, HTML to succeed
        def side_effect(url, **kwargs):
            if "format=json" in url:
                raise httpx.ConnectError("no JSON")
            if "medium.com/_/api/" in url:
                return httpx.Response(404)
            return httpx.Response(200, text="<html></html>")

        html_content = """<!DOCTYPE html>
<html>
<head>
<title>Test Article</title>
<meta name="description" content="A test article description.">
<meta property="og:title" content="OG Title">
<meta property="og:description" content="OG description here.">
<meta property="og:image" content="https://example.com/cover.jpg">
<meta property="og:site_name" content="Test Publication">
</head>
<body></body>
</html>"""

        with patch("fourdpocket.processors.medium._try_internal_api", return_value=None):
            with patch("fourdpocket.processors.medium._try_json_endpoint", return_value=None):
                respx_mock.get(url__regex=r"https://medium\.com/@user/test-article.*").mock(
                    return_value=httpx.Response(200, text=html_content)
                )
                proc = MediumProcessor()
                result = asyncio.run(proc.process(url))

        assert result.source_platform == "medium"
        assert result.status.value == "success"
        assert result.title == "OG Title"

    @respx.mock(assert_all_called=False)
    def test_html_fallback_httperror(self, respx_mock):
        """HTML fetch raises HTTPStatusError → partial."""
        url = "https://medium.com/@user/test-abc123"

        def side_effect(request):
            # respx passes Request object, not URL string
            req_url = str(request.url)
            if "format=json" in req_url:
                raise httpx.ConnectError("no JSON")
            if "medium.com/_/api/" in req_url:
                return httpx.Response(404)
            raise httpx.HTTPStatusError("403 Forbidden", request=request, response=MagicMock(status_code=403))

        with patch("fourdpocket.processors.medium._try_internal_api", return_value=None):
            with patch("fourdpocket.processors.medium._try_json_endpoint", return_value=None):
                respx_mock.get(url__regex=r"https://medium\.com/@user/test-abc123").mock(
                    side_effect=side_effect
                )
                proc = MediumProcessor()
                result = asyncio.run(proc.process(url))

        assert result.status.value == "partial"
        assert "403" in result.error


class TestTryInternalApi:
    """_try_internal_api with curl_cffi mocking."""

    def test_returns_payload_on_success(self):
        """curl_cffi returns 200 with valid JSON → payload returned."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ']}while(1);</x>{"payload": {"value": {"title": "API Article"}}}'

        mock_cffi_get = MagicMock(return_value=mock_response)

        import curl_cffi.requests as cffi_requests
        with patch.object(cffi_requests, "get", mock_cffi_get):
            result = _try_internal_api("https://medium.com/@user/article-abc123def")

        assert result is not None
        assert "value" in result

    def test_returns_none_on_404(self):
        """curl_cffi returns 404 → None."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_cffi_get = MagicMock(return_value=mock_response)

        import curl_cffi.requests as cffi_requests
        with patch.object(cffi_requests, "get", mock_cffi_get):
            result = _try_internal_api("https://medium.com/@user/nonexistent-abc123")

        assert result is None

    def test_returns_none_on_import_error(self, monkeypatch):
        """curl_cffi not installed → None."""
        import sys
        monkeypatch.delitem(sys.modules, "curl_cffi", raising=False)
        result = _try_internal_api("https://medium.com/@user/article-abc123def")
        assert result is None

    def test_returns_none_on_post_id_extraction_failure(self):
        """URL without valid post ID → None (no curl_cffi call)."""
        import sys
        before = sys.modules.get("curl_cffi")
        result = _try_internal_api("https://medium.com/@user/no-valid-id")
        assert result is None
        after = sys.modules.get("curl_cffi")
        assert after is before
