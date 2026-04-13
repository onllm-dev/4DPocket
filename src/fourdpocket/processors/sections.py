"""Structured content sections — typed primitives produced by every processor.

Sections replace the old "single string of content" output with a flat,
typed list. Downstream chunking, embedding, entity extraction, and
search-result snippets all become section-aware.

Schema rationale lives in `.omc/research/content-sections-decision.md`
but the short version: borrow unstructured.io's element vocabulary
(string discriminator, not class hierarchy), llama-index's TextNode
parent/order pattern, and Docling's heading-path chunking trick.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable, Literal

# Vocabulary chosen to cover web articles, forum threads, Q&A, video,
# audio, PDFs, and images without bloating into a per-platform enum.
SectionKind = Literal[
    # primary content
    "title", "subtitle", "heading", "paragraph", "abstract", "summary",
    # rich blocks
    "list_item", "quote", "code", "table", "figure", "caption", "formula",
    # social / threaded
    "post", "comment", "reply", "quoted_post",
    # Q&A
    "question", "answer", "accepted_answer",
    # video / audio
    "transcript_segment", "chapter",
    # documents
    "page", "header", "footer", "page_number", "footnote",
    # images
    "ocr_text", "visual_caption", "alt_text",
    # catch-all
    "metadata_block", "uncategorized",
]

# Search-time signal — boost "main" content above "boilerplate" / "promotional".
Role = Literal["main", "supplemental", "navigational", "promotional", "boilerplate"]


@dataclass(frozen=True)
class Section:
    """One structurally-typed unit of content from a processor.

    Frozen so processors can't accidentally mutate after returning.
    Use ``Section(...)._replace(...)`` style via ``dataclasses.replace`` if
    you need to derive a new one.
    """

    # identity + ordering
    id: str
    kind: SectionKind
    order: int = 0
    parent_id: str | None = None
    depth: int = 0

    # payload
    text: str = ""
    raw_html: str | None = None
    role: Role = "main"

    # provenance
    source_url: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    page_no: int | None = None
    timestamp_start_s: float | None = None
    timestamp_end_s: float | None = None

    # who / when (threaded sources)
    author: str | None = None
    author_id: str | None = None
    score: int | None = None
    upvotes: int | None = None
    is_accepted: bool = False
    created_at: str | None = None

    # kind-specific knobs without polluting top-level
    extra: dict = field(default_factory=dict)


def make_section_id(seed: str, order: int) -> str:
    """Stable, short, deterministic id from (seed, order).

    `seed` is typically the source URL or processor name. Used so the same
    URL re-processed twice produces the same section ids — important for
    incremental re-chunking.
    """
    payload = f"{seed}::{order}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def sections_to_text(sections: Iterable[Section]) -> str:
    """Render a list of sections into a single plaintext blob.

    Used to populate the legacy ``Item.content`` field for back-compat
    (search fallbacks, raw display, anything that hasn't been migrated to
    section-aware reads). Strips boilerplate/promotional sections — they
    pollute search.

    Format intent: each section becomes one paragraph (separated by
    ``\\n\\n``) so the existing paragraph-splitter still works as a
    fallback if the section list is missing downstream.
    """
    parts: list[str] = []
    for s in sections:
        if s.role in ("boilerplate", "promotional"):
            continue
        text = (s.text or "").strip()
        if not text:
            continue
        if s.kind == "title":
            parts.append(f"# {text}")
        elif s.kind == "heading":
            level = max(1, min(6, s.depth + 1))
            parts.append(f"{'#' * level} {text}")
        elif s.kind == "subtitle":
            parts.append(f"## {text}")
        elif s.kind == "list_item":
            parts.append(f"- {text}")
        elif s.kind == "code":
            lang = s.extra.get("language", "") if s.extra else ""
            parts.append(f"```{lang}\n{text}\n```")
        elif s.kind == "quote":
            parts.append(f"> {text}")
        elif s.kind in ("comment", "reply", "post"):
            author = f"@{s.author}" if s.author else "anon"
            score = f" ({s.score})" if s.score is not None else ""
            indent = "  " * max(0, s.depth - 1) if s.depth > 1 else ""
            parts.append(f"{indent}{author}{score}: {text}")
        elif s.kind == "transcript_segment":
            ts = (
                f"[{int(s.timestamp_start_s):d}s] "
                if s.timestamp_start_s is not None
                else ""
            )
            parts.append(f"{ts}{text}")
        else:
            parts.append(text)
    return "\n\n".join(parts)


def section_summary_for_metadata(sections: Iterable[Section]) -> dict:
    """Aggregate counts/indicators useful for filters in item_metadata."""
    by_kind: dict[str, int] = {}
    by_role: dict[str, int] = {}
    for s in sections:
        by_kind[s.kind] = by_kind.get(s.kind, 0) + 1
        by_role[s.role] = by_role.get(s.role, 0) + 1
    return {"section_counts": by_kind, "role_counts": by_role}
