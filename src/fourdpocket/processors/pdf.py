"""PDF processor - full-text extraction via PyMuPDF."""

import io
import logging

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


@register_processor
class PDFProcessor(BaseProcessor):
    """Extract text and metadata from PDF files."""

    url_patterns = []  # file-upload based, not URL-matched
    priority = -1

    async def process(self, url: str, file_data: bytes = b"", filename: str = "", **kwargs) -> ProcessorResult:
        if not file_data:
            return ProcessorResult(
                title=filename or "Unknown PDF",
                item_type="pdf",
                source_platform="generic",
                status=ProcessorStatus.failed,
                error="No file data provided",
            )

        metadata = {"filename": filename}
        full_text = None

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=file_data, filetype="pdf")

            # Extract metadata
            pdf_meta = doc.metadata
            if pdf_meta:
                if pdf_meta.get("title"):
                    metadata["pdf_title"] = pdf_meta["title"]
                if pdf_meta.get("author"):
                    metadata["author"] = pdf_meta["author"]
                if pdf_meta.get("subject"):
                    metadata["subject"] = pdf_meta["subject"]
                if pdf_meta.get("keywords"):
                    metadata["keywords"] = pdf_meta["keywords"]
                if pdf_meta.get("creationDate"):
                    metadata["creation_date"] = pdf_meta["creationDate"]

            metadata["page_count"] = len(doc)

            # Extract text from all pages
            text_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text().strip()
                if page_text:
                    text_parts.append(page_text)

            doc.close()

            if text_parts:
                full_text = "\n\n---\n\n".join(text_parts)
                metadata["text_length"] = len(full_text)
                metadata["pages_with_text"] = len(text_parts)

        except ImportError:
            return ProcessorResult(
                title=filename or "Unknown PDF",
                item_type="pdf",
                source_platform="generic",
                status=ProcessorStatus.failed,
                error="PyMuPDF (fitz) not installed",
                metadata=metadata,
            )
        except Exception as e:
            logger.error("PDF extraction failed: %s", e)
            return ProcessorResult(
                title=filename or "Unknown PDF",
                item_type="pdf",
                source_platform="generic",
                status=ProcessorStatus.failed,
                error=f"PDF extraction error: {str(e)[:200]}",
                metadata=metadata,
            )

        title = metadata.get("pdf_title") or filename or "Uploaded PDF"
        description_parts = []
        if metadata.get("author"):
            description_parts.append(f"By {metadata['author']}")
        description_parts.append(f"{metadata.get('page_count', 0)} pages")
        description = " | ".join(description_parts)

        # Generate summary from first 500 chars
        summary_text = full_text[:500] + "..." if full_text and len(full_text) > 500 else full_text

        return ProcessorResult(
            title=title,
            description=description,
            content=full_text[:200000] if full_text else None,  # cap at 200KB
            raw_content=None,
            media=[],
            metadata=metadata,
            source_platform="generic",
            item_type="pdf",
            status=ProcessorStatus.success,
        )
