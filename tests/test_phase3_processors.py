"""Phase 3 processor tests — PDF, Medium, Substack, Image sections."""

from __future__ import annotations

import asyncio
import io

import httpx
import pytest
import respx

# ─── PDF ──────────────────────────────────────────────


def _make_test_pdf() -> bytes:
    """Build a tiny multi-page PDF with markdown-detectable headings."""
    pymupdf = pytest.importorskip("pymupdf")

    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((50, 100), "Introduction\n\nFirst page body about widgets.")
    p2 = doc.new_page()
    p2.insert_text((50, 100), "Methods\n\nSecond page body about results.")
    bio = io.BytesIO()
    doc.save(bio)
    doc.close()
    return bio.getvalue()


def test_pdf_emits_page_sections():
    from fourdpocket.processors.pdf import PDFProcessor

    pdf_bytes = _make_test_pdf()
    proc = PDFProcessor()
    result = asyncio.run(proc.process(
        url="", file_data=pdf_bytes, filename="report.pdf",
    ))

    assert result.item_type == "pdf"
    sections = result.sections
    pages = [s for s in sections if s.kind == "page"]
    assert len(pages) >= 2
    # Each page should carry its page_no
    assert pages[0].page_no == 1
    assert pages[1].page_no == 2
    # Body sections inherit page_no
    body = [s for s in sections if s.kind in ("paragraph", "heading")]
    assert all(s.page_no in (1, 2) for s in body)


def test_pdf_metadata_extracted():
    from fourdpocket.processors.pdf import PDFProcessor

    pdf_bytes = _make_test_pdf()
    result = asyncio.run(PDFProcessor().process(
        url="", file_data=pdf_bytes, filename="report.pdf",
    ))
    assert result.metadata.get("page_count") == 2
    assert result.metadata.get("extraction_mode") in ("pymupdf4llm", "pymupdf")


# ─── Medium ─────────────────────────────────────────


MEDIUM_PAYLOAD = {
    "payload": {
        "value": {
            "title": "Why X matters",
            "creatorId": "u1",
            "content": {
                "subtitle": "A short take.",
                "bodyModel": {
                    "paragraphs": [
                        {"type": 3, "text": "Background"},
                        {"type": 1, "text": "I want to write about X."},
                        {"type": 6, "text": "Important quote here."},
                        {"type": 8, "text": "code = 'snippet'"},
                    ],
                },
            },
            "virtuals": {
                "totalClapCount": 100,
                "readingTime": 4.2,
                "wordCount": 800,
                "tags": [{"slug": "python"}, {"slug": "programming"}],
                "previewImage": {"imageId": "abc.jpg"},
            },
            "firstPublishedAt": 1700000000,
        },
        "references": {"User": {"u1": {"name": "Some Author"}}},
    },
}


def test_medium_json_endpoint_emits_typed_sections():
    import sys
    from unittest.mock import patch
    from fourdpocket.processors.medium import MediumProcessor

    proc = MediumProcessor()

    # Patch out curl_cffi so _try_json_endpoint falls back to httpx,
    # which respx can intercept. Also patch _try_internal_api since the
    # URL has no hex post ID but the patch avoids any live network call.
    with patch("fourdpocket.processors.medium._try_internal_api", return_value=None):
        with patch.dict(sys.modules, {"curl_cffi": None, "curl_cffi.requests": None}):
            with respx.mock(assert_all_called=False) as r:
                # JSON has the anti-JSONP prefix
                prefix = "])}while(1);</x>"
                body = prefix + __import__("json").dumps(MEDIUM_PAYLOAD)
                r.get(url__regex=r"https://medium\.com/@me/why-x-matters\?format=json").mock(
                    return_value=httpx.Response(200, text=body)
                )
                result = asyncio.run(proc.process(
                    "https://medium.com/@me/why-x-matters"
                ))

    sections = result.sections
    titles = [s for s in sections if s.kind == "title"]
    assert titles and titles[0].text == "Why X matters"

    headings = [s for s in sections if s.kind == "heading"]
    assert any(h.text == "Background" for h in headings)
    paragraphs = [s for s in sections if s.kind == "paragraph"]
    assert any("write about X" in p.text for p in paragraphs)

    quotes = [s for s in sections if s.kind == "quote"]
    assert quotes and quotes[0].text == "Important quote here."

    code = [s for s in sections if s.kind == "code"]
    assert code and "snippet" in code[0].text


# ─── Substack ───────────────────────────────────────


SUBSTACK_API_PAYLOAD = {
    "title": "The Newsletter Post",
    "subtitle": "An interesting take",
    "body_html": (
        "<h1>Heading One</h1>"
        "<p>First body paragraph.</p>"
        "<h2>Sub heading</h2>"
        "<p>Second body paragraph.</p>"
        "<blockquote>A quote block</blockquote>"
    ),
    "cover_image": "https://substackcdn.com/cover.jpg",
    "post_date": "2026-01-01T00:00:00Z",
    "publishedBylines": [{"name": "Author Person"}],
    "wordcount": 800,
    "comment_count": 5,
    "reactions": 100,
    "postTags": [{"name": "tech"}],
}


def test_substack_api_emits_typed_sections():
    from fourdpocket.processors.substack import SubstackProcessor

    proc = SubstackProcessor()
    with respx.mock(assert_all_called=False) as r:
        r.get("https://example.substack.com/api/v1/posts/the-post").mock(
            return_value=httpx.Response(200, json=SUBSTACK_API_PAYLOAD)
        )
        result = asyncio.run(proc.process(
            "https://example.substack.com/p/the-post"
        ))

    assert result.title == "The Newsletter Post"
    sections = result.sections
    titles = [s for s in sections if s.kind == "title"]
    assert titles and titles[0].text == "The Newsletter Post"
    subtitles = [s for s in sections if s.kind == "subtitle"]
    assert subtitles and subtitles[0].text == "An interesting take"

    headings = [s for s in sections if s.kind == "heading"]
    heading_texts = {h.text for h in headings}
    assert "Heading One" in heading_texts
    assert "Sub heading" in heading_texts

    quotes = [s for s in sections if s.kind == "quote"]
    assert quotes and quotes[0].text == "A quote block"

    assert result.metadata["author"] == "Author Person"
    assert result.metadata["newsletter_name"] == "example"


# ─── Image ─────────────────────────────────────────


def _make_test_image_with_text() -> bytes:
    """Build a tiny PNG with no real text — OCR may return empty,
    that's fine; we test the section shape, not OCR accuracy."""
    pytest.importorskip("PIL")
    from PIL import Image

    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def test_image_emits_metadata_section():
    from fourdpocket.processors.image import ImageProcessor

    img_bytes = _make_test_image_with_text()
    result = asyncio.run(ImageProcessor().process(
        url="", file_data=img_bytes, filename="cool.png",
    ))

    sections = result.sections
    titles = [s for s in sections if s.kind == "title"]
    assert titles and titles[0].text == "cool.png"
    metas = [s for s in sections if s.kind == "metadata_block"]
    assert metas and "100x100" in metas[0].text
    # OCR may or may not run depending on system tesseract — both fine.
    assert result.item_type == "image"
