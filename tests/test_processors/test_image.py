"""Tests for Image processor (EXIF + OCR)."""
import asyncio
from unittest.mock import MagicMock

from fourdpocket.processors.image import ImageProcessor


class TestExtract:
    """Test image processing with mocked PIL/pytesseract."""

    def test_extract_no_file_data(self):
        """No file data → failed result."""
        processor = ImageProcessor()
        result = asyncio.run(processor.process(
            "https://example.com/image.jpg",
            file_data=b"",
        ))

        assert result.status.value == "failed"
        assert "file data" in result.error.lower()

    def test_url_pattern_matching(self):
        """Image processor is file-upload based, not URL matched."""
        from fourdpocket.processors.registry import match_processor

        proc = match_processor("https://example.com/image.jpg")
        assert type(proc).__name__ == "GenericURLProcessor"


# === PHASE 2A MOPUP ADDITIONS ===
import sys


class TestImageProcess:
    """Full process() tests with PIL/pytesseract mocking."""

    def test_process_with_pil_exif(self, monkeypatch):
        """PIL extracts EXIF metadata successfully; pytesseract unavailable → partial."""
        mock_img = MagicMock()
        mock_img.width = 1920
        mock_img.height = 1080
        mock_img.format = "JPEG"
        mock_img.mode = "RGB"

        mock_exif = MagicMock()
        mock_exif.items.return_value = [
            (271, "Canon"),       # Make
            (305, "Canon PowerShot"),  # Software
            (306, "2024:01:15 10:30:00"),  # DateTime
        ]
        mock_img.getexif.return_value = mock_exif

        def fake_image_open(src):
            return mock_img

        monkeypatch.setattr("PIL.Image.open", fake_image_open)
        # Block pytesseract import so OCR path fails gracefully
        monkeypatch.setitem(sys.modules, "pytesseract", None)

        proc = ImageProcessor()
        result = asyncio.run(proc.process(
            "https://example.com/photo.jpg",
            file_data=b"FAKE_IMAGE_DATA",
            filename="photo.jpg",
        ))

        assert result.metadata["width"] == 1920
        assert result.metadata["height"] == 1080
        assert result.metadata["format"] == "JPEG"
        assert result.metadata["camera_make"] == "Canon"
        assert result.metadata["taken_at"] == "2024:01:15 10:30:00"
        assert result.status.value == "partial"  # because OCR is not available

    def test_process_with_ocr(self, monkeypatch):
        """pytesseract extracts OCR text → ocr_text section emitted."""
        mock_img = MagicMock()
        mock_img.width = 800
        mock_img.height = 600
        mock_img.format = "PNG"
        mock_img.mode = "RGBA"
        mock_img.getexif.return_value = None

        def fake_image_open(src):
            return mock_img

        monkeypatch.setattr("PIL.Image.open", fake_image_open)
        monkeypatch.setattr("pytesseract.image_to_string", lambda *a: "Extracted OCR text from image")

        proc = ImageProcessor()
        result = asyncio.run(proc.process(
            "https://example.com/screenshot.png",
            file_data=b"FAKE_PNG_DATA",
            filename="screenshot.png",
        ))

        assert result.status.value == "success"
        assert result.metadata["ocr_extracted"] is True
        section_kinds = {s.kind for s in result.sections}
        assert "ocr_text" in section_kinds
        ocr_section = next(s for s in result.sections if s.kind == "ocr_text")
        assert "Extracted OCR text" in ocr_section.text

    def test_process_pillow_not_installed(self, monkeypatch):
        """Pillow not installed → partial result."""
        # Block PIL imports at the sys.modules level
        import types
        fake_pil = types.ModuleType("PIL")
        fake_pil.Image = types.ModuleType("PIL.Image")
        monkeypatch.setitem(sys.modules, "PIL", fake_pil)
        monkeypatch.setitem(sys.modules, "PIL.Image", fake_pil.Image)
        monkeypatch.setitem(sys.modules, "PIL.ExifTags", None)

        proc = ImageProcessor()
        result = asyncio.run(proc.process(
            "https://example.com/photo.jpg",
            file_data=b"FAKE_IMAGE_DATA",
            filename="photo.jpg",
        ))

        assert result.status.value == "partial"
        assert "pillow_error" in result.metadata or "Pillow" in result.metadata.get("pillow_error", "")

    def test_process_pytesseract_not_installed(self, monkeypatch):
        """pytesseract not installed → partial, no OCR."""
        mock_img = MagicMock()
        mock_img.width = 1024
        mock_img.height = 768
        mock_img.format = "JPEG"
        mock_img.mode = "RGB"
        mock_img.getexif.return_value = None

        def fake_image_open(src):
            return mock_img

        monkeypatch.setattr("PIL.Image.open", fake_image_open)
        # Block pytesseract import
        monkeypatch.setitem(sys.modules, "pytesseract", None)

        proc = ImageProcessor()
        result = asyncio.run(proc.process(
            "https://example.com/photo.jpg",
            file_data=b"FAKE_IMAGE_DATA",
            filename="photo.jpg",
        ))

        assert result.status.value == "partial"
        assert "ocr_error" in result.metadata
        ocr_sections = [s for s in result.sections if s.kind == "ocr_text"]
        assert len(ocr_sections) == 0

    def test_process_no_filename_defaults_title(self, monkeypatch):
        """No filename → title defaults to 'Uploaded Image'."""
        mock_img = MagicMock()
        mock_img.width = 100
        mock_img.height = 100
        mock_img.format = "GIF"
        mock_img.mode = "P"
        mock_img.getexif.return_value = None

        def fake_image_open(src):
            return mock_img

        monkeypatch.setattr("PIL.Image.open", fake_image_open)
        monkeypatch.setitem(sys.modules, "pytesseract", None)

        proc = ImageProcessor()
        result = asyncio.run(proc.process(
            "https://example.com/image.gif",
            file_data=b"FAKE_GIF",
        ))

        assert result.title == "Uploaded Image"

    def test_process_pil_exception_continues(self, monkeypatch):
        """PIL raises exception during EXIF → metadata has error, process continues."""
        mock_img = MagicMock()
        mock_img.width = 640
        mock_img.height = 480
        mock_img.format = "JPEG"
        mock_img.mode = "RGB"
        mock_img.getexif.side_effect = RuntimeError("EXIF corrupt")

        def fake_image_open(src):
            return mock_img

        monkeypatch.setattr("PIL.Image.open", fake_image_open)
        monkeypatch.setattr("pytesseract.image_to_string", lambda *a: "Text from OCR")

        proc = ImageProcessor()
        result = asyncio.run(proc.process(
            "https://example.com/corrupt.jpg",
            file_data=b"FAKE_DATA",
            filename="corrupt.jpg",
        ))

        assert result.metadata["exif_error"] is not None
        assert result.status.value == "success"
