"""Image processor - EXIF extraction and OCR."""

import io
import logging

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


@register_processor
class ImageProcessor(BaseProcessor):
    """Extract text and metadata from uploaded images."""

    url_patterns = []  # file-upload based, not URL-matched
    priority = -1

    async def process(self, url: str, file_data: bytes = b"", filename: str = "", **kwargs) -> ProcessorResult:
        if not file_data:
            return ProcessorResult(
                title=filename or "Unknown Image",
                item_type="image",
                source_platform="generic",
                status=ProcessorStatus.failed,
                error="No file data provided",
            )

        metadata = {"filename": filename}
        ocr_text = None
        media = []

        # Extract EXIF data via Pillow
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
                exif_dict = {}
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

        # OCR via pytesseract
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(file_data))
            ocr_text = pytesseract.image_to_string(img).strip()
            if ocr_text:
                metadata["ocr_extracted"] = True
                metadata["ocr_length"] = len(ocr_text)
            else:
                metadata["ocr_extracted"] = False
        except ImportError:
            logger.debug("pytesseract not installed, skipping OCR")
            metadata["ocr_error"] = "pytesseract not installed"
        except Exception as e:
            logger.warning("OCR failed: %s", e)
            metadata["ocr_error"] = str(e)[:200]

        title = filename or "Uploaded Image"
        description_parts = []
        if metadata.get("width") and metadata.get("height"):
            description_parts.append(f"{metadata['width']}x{metadata['height']} {metadata.get('format', 'image')}")
        if metadata.get("camera_make"):
            description_parts.append(f"Camera: {metadata['camera_make']} {metadata.get('camera_model', '')}")
        description = " | ".join(description_parts) if description_parts else None

        status = ProcessorStatus.success
        error = None
        if not ocr_text and "ocr_error" in metadata:
            status = ProcessorStatus.partial
            error = "OCR unavailable"

        return ProcessorResult(
            title=title,
            description=description,
            content=ocr_text,
            media=media,
            metadata=metadata,
            source_platform="generic",
            item_type="image",
            status=status,
            error=error,
        )
