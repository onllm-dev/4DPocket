"""PDF processor — page-level structured extraction.

Per R&D memo:
  * Default: ``pymupdf4llm`` (~50MB, fast, native markdown output with
    page boundaries + heading detection). Falls back to plain
    ``pymupdf`` (already in deps) when pymupdf4llm isn't installed —
    same engine, less polish.
  * Sections: ``page`` per PDF page, plus inline ``heading`` /
    ``paragraph`` extracted from the markdown stream so we don't lose
    document structure.
  * Auto-detect scanned PDFs via text-density heuristic; flag for OCR
    so a follow-up enrichment stage can pick them up. We don't run OCR
    inline — Marker/PaddleOCR are heavy and would block the worker.
"""

from __future__ import annotations

import logging
import re

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section

logger = logging.getLogger(__name__)


def _split_markdown_into_sections(
    markdown: str,
    page_no: int | None,
    parent_id: str | None,
    start_order: int,
) -> tuple[list[Section], int]:
    """Split a markdown blob into heading + paragraph sections.

    Returns ``(sections, next_order)``. Used both per-page and for the
    whole document when page boundaries aren't meaningful.
    """
    sections: list[Section] = []
    order = start_order
    current_heading_id = parent_id
    current_heading_depth = 0
    body: list[str] = []

    def _flush():
        nonlocal order
        if not body:
            return
        text = "\n".join(body).strip()
        if text:
            sections.append(Section(
                id=f"pdf_p_{order}", kind="paragraph", order=order,
                parent_id=current_heading_id, depth=current_heading_depth + 1,
                role="main", text=text, page_no=page_no,
            ))
            order += 1
        body.clear()

    for line in markdown.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            _flush()
            level = len(m.group(1))
            current_heading_id = f"pdf_h_{order}"
            current_heading_depth = level - 1
            sections.append(Section(
                id=current_heading_id, kind="heading", order=order,
                parent_id=parent_id, depth=current_heading_depth,
                role="main", text=m.group(2), page_no=page_no,
            ))
            order += 1
        else:
            body.append(line)
    _flush()
    return sections, order


@register_processor
class PDFProcessor(BaseProcessor):
    """Extract text + structured sections from a PDF blob."""

    url_patterns = []  # file-upload based, not URL-matched
    priority = -1

    async def process(
        self, url: str, file_data: bytes = b"", filename: str = "", **kwargs
    ) -> ProcessorResult:
        if not file_data:
            return ProcessorResult(
                title=filename or "Unknown PDF",
                item_type="pdf", source_platform="generic",
                status=ProcessorStatus.failed,
                error="No file data provided",
            )

        metadata: dict = {"filename": filename}
        sections: list[Section] = []
        full_text_for_compat = ""

        # Try pymupdf4llm (markdown + better headings) first.
        used_llm = False
        try:
            import pymupdf  # type: ignore
            import pymupdf4llm  # type: ignore

            doc = pymupdf.open(stream=file_data, filetype="pdf")
            metadata["page_count"] = len(doc)
            self._extract_pdf_metadata(doc, metadata)

            # pymupdf4llm.to_markdown returns either str or list[dict]
            # depending on flags. We use page_chunks=True to get a list
            # of page-level dicts {text, metadata: {page}, ...}.
            page_chunks = pymupdf4llm.to_markdown(
                doc, page_chunks=True, write_images=False, show_progress=False,
            )
            doc.close()
            used_llm = True

            order = 0
            page_section_ids: list[str] = []
            md_total: list[str] = []
            for chunk in page_chunks:
                page_no = (chunk.get("metadata") or {}).get("page", len(page_section_ids)) + 1
                md = (chunk.get("text") or "").strip()
                if not md:
                    continue
                # One ``page`` section per page (navigational marker —
                # keeps page_no on chunk metadata even for one-page docs).
                page_id = f"pdf_pg_{page_no}"
                page_section_ids.append(page_id)
                sections.append(Section(
                    id=page_id, kind="page", order=order, role="navigational",
                    text=f"Page {page_no}", page_no=page_no,
                ))
                order += 1
                page_sections, order = _split_markdown_into_sections(
                    md, page_no=page_no, parent_id=page_id, start_order=order,
                )
                sections.extend(page_sections)
                md_total.append(md)

            full_text_for_compat = "\n\n".join(md_total)
            if full_text_for_compat:
                metadata["text_length"] = len(full_text_for_compat)
                metadata["pages_with_text"] = len(page_section_ids)

        except ImportError:
            logger.debug("pymupdf4llm unavailable, falling back to pymupdf")

        # Fallback to plain pymupdf if pymupdf4llm wasn't available
        if not sections:
            try:
                import pymupdf  # type: ignore

                doc = pymupdf.open(stream=file_data, filetype="pdf")
                metadata["page_count"] = len(doc)
                self._extract_pdf_metadata(doc, metadata)

                order = 0
                page_text_acc: list[str] = []
                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    text = (page.get_text() or "").strip()
                    if not text:
                        continue
                    page_no = page_idx + 1
                    page_id = f"pdf_pg_{page_no}"
                    sections.append(Section(
                        id=page_id, kind="page", order=order, role="navigational",
                        text=f"Page {page_no}", page_no=page_no,
                    ))
                    order += 1
                    sections.append(Section(
                        id=f"pdf_t_{page_no}", kind="paragraph", order=order,
                        parent_id=page_id, role="main",
                        text=text, page_no=page_no,
                    ))
                    order += 1
                    page_text_acc.append(text)
                doc.close()
                full_text_for_compat = "\n\n".join(page_text_acc)
                metadata["pages_with_text"] = len(page_text_acc)
            except ImportError:
                return ProcessorResult(
                    title=filename or "Unknown PDF",
                    item_type="pdf", source_platform="generic",
                    status=ProcessorStatus.failed,
                    error="PyMuPDF (fitz) not installed",
                    metadata=metadata,
                )
            except Exception as e:
                logger.error("PDF extraction failed: %s", e)
                return ProcessorResult(
                    title=filename or "Unknown PDF",
                    item_type="pdf", source_platform="generic",
                    status=ProcessorStatus.failed,
                    error=f"PDF extraction error: {str(e)[:200]}",
                    metadata=metadata,
                )

        # Scan-detection heuristic: very low text density per page → flag.
        # The downstream OCR enrichment can pick this up later (Marker).
        if metadata.get("pages_with_text", 0) > 0:
            avg_chars = len(full_text_for_compat) // max(metadata["pages_with_text"], 1)
            if avg_chars < 50:
                metadata["likely_scanned"] = True

        metadata["extraction_mode"] = "pymupdf4llm" if used_llm else "pymupdf"

        title = metadata.get("pdf_title") or filename or "Uploaded PDF"
        description_parts = []
        if metadata.get("author"):
            description_parts.append(f"By {metadata['author']}")
        description_parts.append(f"{metadata.get('page_count', 0)} pages")
        description = " | ".join(description_parts)

        return ProcessorResult(
            title=title,
            description=description,
            content=None,  # derived from sections by fetcher
            raw_content=full_text_for_compat[:200000] if full_text_for_compat else None,
            media=[],
            metadata=metadata,
            source_platform="generic",
            item_type="pdf",
            status=ProcessorStatus.success,
            sections=sections,
        )

    @staticmethod
    def _extract_pdf_metadata(doc, metadata: dict) -> None:
        try:
            pdf_meta = doc.metadata or {}
        except Exception:
            return
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
