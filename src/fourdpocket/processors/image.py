"""Image processor — EXIF + OCR + structured sections.

OCR via pytesseract (already in deps; system tesseract binary required).
Per R&D memo, PaddleOCR offers higher accuracy but pulls 500MB of
PyTorch weights — too heavy for the default install. Tesseract stays
the default; users can swap in a vision-language model via the AI
provider in a follow-up if they want.

Sections:
  * ``visual_caption`` — placeholder for AI-generated description
    (only emitted when an opt-in vision provider returns text)
  * ``ocr_text``  — extracted OCR text, role=main
  * ``metadata_block`` — EXIF camera/timestamp summary, role=supplemental
"""

from __future__ import annotations

import io
import logging

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)


@register_processor
class ImageProcessor(BaseProcessor):
    """EXIF + OCR extraction with sectioned output."""

    url_patterns = []
    priority = -1

    async def process(
        self, url: str, file_data: bytes = b"", filename: str = "", **kwargs
    ) -> ProcessorResult:
        if not file_data:
            return ProcessorResult(
                title=filename or "Unknown Image",
                item_type="image", source_platform="generic",
                status=ProcessorStatus.failed,
                error="No file data provided",
            )

        metadata: dict = {"filename": filename}
        ocr_text: str | None = None
        sections: list[Section] = []
        seed = filename or "image"

        # ─── EXIF + dimensions ───
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            img = Image.open(io.BytesIO(file_data))
            metadata["width"] = img.width
            metadata["height"] = img.height
            metadata["format"] = img.format
            metadata["mode"] = img.mode

            exif_data = img.getexif()
            if exif_data:
                exif_dict: dict = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    try:
                        exif_dict[tag_name] = str(value)
                    except Exception:
                        pass
                if exif_dict:
                    metadata["exif"] = exif_dict
                    if "DateTime" in exif_dict:
                        metadata["taken_at"] = exif_dict["DateTime"]
                    if "Make" in exif_dict:
                        metadata["camera_make"] = exif_dict["Make"]
                    if "Model" in exif_dict:
                        metadata["camera_model"] = exif_dict["Model"]
        except ImportError:
            metadata["pillow_error"] = "Pillow not installed"
        except Exception as e:
            logger.warning("EXIF extraction failed: %s", e)
            metadata["exif_error"] = str(e)[:200]

        # ─── OCR via pytesseract ───
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(file_data))
            ocr_text = (pytesseract.image_to_string(img) or "").strip()
            metadata["ocr_extracted"] = bool(ocr_text)
            if ocr_text:
                metadata["ocr_length"] = len(ocr_text)
        except ImportError:
            logger.debug("pytesseract not installed, skipping OCR")
            metadata["ocr_error"] = "pytesseract not installed"
        except Exception as e:
            logger.warning("OCR failed: %s", e)
            metadata["ocr_error"] = str(e)[:200]

        # ─── Sections ───
        order = 0
        if filename:
            sections.append(Section(
                id=make_section_id(seed, order), kind="title", order=order,
                role="main", text=filename,
            ))
            order += 1
        if metadata.get("width") and metadata.get("height"):
            meta_text_parts = [
                f"{metadata['width']}x{metadata['height']} {metadata.get('format', 'image')}"
            ]
            if metadata.get("camera_make"):
                meta_text_parts.append(
                    f"Camera: {metadata['camera_make']} {metadata.get('camera_model', '')}"
                )
            if metadata.get("taken_at"):
                meta_text_parts.append(f"Taken: {metadata['taken_at']}")
            sections.append(Section(
                id=make_section_id(seed, order), kind="metadata_block",
                order=order, role="supplemental",
                text=" | ".join(meta_text_parts),
            ))
            order += 1
        if ocr_text:
            sections.append(Section(
                id=make_section_id(seed, order), kind="ocr_text", order=order,
                role="main", text=ocr_text,
            ))
            order += 1

        title = filename or "Uploaded Image"
        description_parts = []
        if metadata.get("width") and metadata.get("height"):
            description_parts.append(
                f"{metadata['width']}x{metadata['height']} {metadata.get('format', 'image')}"
            )
        if metadata.get("camera_make"):
            description_parts.append(
                f"Camera: {metadata['camera_make']} {metadata.get('camera_model', '')}"
            )
        description = " | ".join(description_parts) if description_parts else None

        status = ProcessorStatus.success
        error = None
        if not ocr_text and "ocr_error" in metadata:
            status = ProcessorStatus.partial
            error = "OCR unavailable"

        return ProcessorResult(
            title=title,
            description=description,
            content=None,
            media=[],
            metadata=metadata,
            source_platform="generic",
            item_type="image",
            status=status,
            error=error,
            sections=sections,
        )
