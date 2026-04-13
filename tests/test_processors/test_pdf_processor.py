"""Tests for PDF processor."""
import asyncio

from fourdpocket.processors.pdf import PDFProcessor, _split_markdown_into_sections


class TestExtract:
    """Test PDF processing with mocked PyMuPDF."""

    def test_extract_no_file_data(self):
        """No file data → failed result."""
        processor = PDFProcessor()
        result = asyncio.run(processor.process(
            "https://example.com/document.pdf",
            file_data=b"",
            filename="empty.pdf",
        ))

        assert result.status.value == "failed"
        assert "file data" in result.error.lower()

    def test_split_markdown_into_sections(self):
        """Markdown split into typed heading + paragraph sections."""
        markdown = """# Main Title

## Subtitle

Some paragraph text here.

### Deep heading

More content under a deeper heading.

Plain paragraph without heading."""

        sections, next_order = _split_markdown_into_sections(
            markdown, page_no=1, parent_id="pdf_pg_1", start_order=0
        )

        section_kinds = [s.kind for s in sections]
        assert "heading" in section_kinds  # # Main Title
        assert "heading" in section_kinds  # ## Subtitle
        assert "heading" in section_kinds  # ### Deep heading
        assert "paragraph" in section_kinds

        # Check depth for headings
        heading_sections = [s for s in sections if s.kind == "heading"]
        assert heading_sections[0].depth == 0  # # Main Title
        assert heading_sections[1].depth == 1  # ## Subtitle
        assert heading_sections[2].depth == 2  # ### Deep heading

        # Page number propagated
        for s in sections:
            assert s.page_no == 1

    def test_url_pattern_matching(self):
        """PDF processor is file-upload based, not URL matched."""
        from fourdpocket.processors.registry import match_processor

        # PDF processor doesn't have URL patterns, so match_processor
        # returns GenericURLProcessor for PDF URLs
        proc = match_processor("https://example.com/document.pdf")
        assert type(proc).__name__ == "GenericURLProcessor"


# === PHASE 2C MOPUP ADDITIONS ===

class TestPyMuPdf4llm:
    """Tests for pymupdf4llm-based PDF processing."""

    def test_process_pymupdf4llm_success(self, monkeypatch):
        """pymupdf4llm returns markdown → sections per page."""
        import pymupdf as pymupdf_mock
        import pymupdf4llm as pymupdf4llm_mock

        # Minimal fake PDF bytes (magic number for a valid PDF is just enough to be parsed)
        fake_pdf = b"%PDF-1.4\ndummy content"

        page_chunks = [
            {"text": "# Page 1\n\nSome text on page one.", "metadata": {"page": 0}},
            {"text": "## Page 2\n\nText on page two.", "metadata": {"page": 1}},
        ]

        monkeypatch.setattr(pymupdf4llm_mock, "to_markdown", lambda doc, **kw: page_chunks)

        class FakeDoc:
            def __init__(self):
                self.metadata = {"title": "Test Doc"}

            def __len__(self):
                return 2

            def close(self):
                pass

        monkeypatch.setattr(pymupdf_mock, "open", lambda *a, **kw: FakeDoc())

        import pymupdf as pm
        import pymupdf4llm as pml

        class FakePage:
            def get_text(self):
                return "page text"

        class FakeDoc2:
            metadata = {"title": "Test Doc", "author": "Test Author"}
            _pages = [FakePage(), FakePage()]

            def __len__(self):
                return len(self._pages)

            def __getitem__(self, idx):
                return self._pages[idx]

            def close(self):
                pass

        monkeypatch.setattr(pm, "open", lambda *a, **kw: FakeDoc2())
        monkeypatch.setattr(pml, "to_markdown", lambda doc, **kw: page_chunks)

        processor = PDFProcessor()
        result = asyncio.run(processor.process(
            "https://example.com/doc.pdf",
            file_data=fake_pdf,
            filename="test.pdf",
        ))

        assert result.status.value == "success"
        assert result.item_type == "pdf"
        section_kinds = [s.kind for s in result.sections]
        assert "page" in section_kinds
        assert result.metadata.get("extraction_mode") == "pymupdf4llm"

    def test_process_pymupdf4llm_import_error(self, monkeypatch):
        """pymupdf4llm ImportError → plain pymupdf fallback."""
        import builtins
        original_import = builtins.__import__

        def raise_import(name, *a, **kw):
            if "pymupdf4llm" in name:
                raise ImportError("No module named 'pymupdf4llm'")
            return original_import(name, *a, **kw)

        monkeypatch.setattr("builtins.__import__", raise_import)

        # Re-import after patch so the processor picks up the failing import
        import sys

        # Remove cached modules so next process() call re-imports
        for mod in list(sys.modules.keys()):
            if "pdf" in mod or "pymupdf" in mod:
                sys.modules.pop(mod, None)

        class FakePage:
            def get_text(self):
                return "fallback text"

        class FakeDoc:
            metadata = {"title": "Fallback Doc"}
            _pages = [FakePage()]

            def __len__(self):
                return len(self._pages)

            def __getitem__(self, idx):
                return self._pages[idx]

            def close(self):
                pass

        import pymupdf as pm
        monkeypatch.setattr(pm, "open", lambda *a, **kw: FakeDoc())

        # Need to re-import processor after clearing cache
        from fourdpocket.processors.pdf import PDFProcessor as PDFProcessorFresh
        processor = PDFProcessorFresh()
        result = asyncio.run(processor.process(
            "https://example.com/doc.pdf",
            file_data=b"%PDF-1.4\n",
            filename="fallback.pdf",
        ))

        assert result.status.value == "success"
        assert result.metadata.get("extraction_mode") == "pymupdf"

    def test_process_both_import_error(self, monkeypatch):
        """Neither pymupdf4llm nor pymupdf available → failed status."""
        import builtins
        original_import = builtins.__import__

        blocked = {"pymupdf4llm", "fitz", "pymupdf"}

        def raise_import(name, *a, **kw):
            if any(b in name for b in blocked):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *a, **kw)

        monkeypatch.setattr("builtins.__import__", raise_import)

        import sys

        for mod in list(sys.modules.keys()):
            if "pdf" in mod or "pymupdf" in mod:
                sys.modules.pop(mod, None)

        from fourdpocket.processors.pdf import PDFProcessor as PDFProcessorFresh
        processor = PDFProcessorFresh()
        result = asyncio.run(processor.process(
            "https://example.com/doc.pdf",
            file_data=b"%PDF-1.4\n",
            filename="broken.pdf",
        ))

        assert result.status.value == "failed"
        assert "not installed" in result.error.lower()

    def test_process_scan_detection(self, monkeypatch):
        """Low text density per page → likely_scanned=True."""
        import pymupdf as pymupdf_mock
        import pymupdf4llm as pymupdf4llm_mock

        # Two pages with minimal text → avg_chars < 50
        page_chunks = [
            {"text": ". .", "metadata": {"page": 0}},
            {"text": ". .", "metadata": {"page": 1}},
        ]

        class FakePage:
            def get_text(self):
                return ". ."

        class FakeDoc:
            metadata = {}
            _pages = [FakePage(), FakePage()]

            def __len__(self):
                return 2

            def __getitem__(self, idx):
                return self._pages[idx]

            def close(self):
                pass

        monkeypatch.setattr(pymupdf_mock, "open", lambda *a, **kw: FakeDoc())
        monkeypatch.setattr(pymupdf4llm_mock, "to_markdown", lambda doc, **kw: page_chunks)

        from fourdpocket.processors.pdf import PDFProcessor as PDFProcessorFresh
        processor = PDFProcessorFresh()
        result = asyncio.run(processor.process(
            "https://example.com/scan.pdf",
            file_data=b"%PDF-1.4\n",
            filename="scanned.pdf",
        ))

        assert result.metadata.get("likely_scanned") is True


class TestExtractPdfMetadata:
    """Tests for PDF metadata extraction."""

    def test_extract_pdf_metadata_full(self):
        """All metadata fields populated."""
        from fourdpocket.processors.pdf import PDFProcessor

        class FakeDoc:
            metadata = {
                "title": "Test Document",
                "author": "Test Author",
                "subject": "Test Subject",
                "keywords": "test, pdf",
                "creationDate": "20240101",
            }

        metadata = {}
        PDFProcessor._extract_pdf_metadata(FakeDoc(), metadata)

        assert metadata.get("pdf_title") == "Test Document"
        assert metadata.get("author") == "Test Author"
        assert metadata.get("subject") == "Test Subject"
        assert metadata.get("keywords") == "test, pdf"
        assert metadata.get("creation_date") == "20240101"
        # creator and producer are not extracted by the code
        assert metadata.get("creator") is None
        assert metadata.get("producer") is None

    def test_extract_pdf_metadata_partial(self):
        """Missing metadata fields → handled gracefully."""
        from fourdpocket.processors.pdf import PDFProcessor

        class FakeDoc:
            metadata = {"title": "Partial Doc"}

        metadata = {}
        PDFProcessor._extract_pdf_metadata(FakeDoc(), metadata)

        assert metadata.get("pdf_title") == "Partial Doc"
        assert metadata.get("creator") is None

    def test_extract_pdf_metadata_exception(self):
        """doc.metadata raises → no crash."""
        from fourdpocket.processors.pdf import PDFProcessor

        class FakeDoc:
            @property
            def metadata(self):
                raise RuntimeError("PDF metadata unavailable")

        metadata = {}
        PDFProcessor._extract_pdf_metadata(FakeDoc(), metadata)

        # Should not raise, metadata unchanged
        assert metadata == {}
