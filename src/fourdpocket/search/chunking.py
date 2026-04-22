"""Text chunking for paragraph-level retrieval.

Splits text into overlapping chunks sized for embedding models.
Uses word-count estimation for token counts (no external deps).

Section-aware (Phase 1+): when called via ``chunk_sections()`` chunks
carry the originating section's kind/role/author/heading-path so
retrieval can filter ("only post bodies, not comments") and result
snippets can render context ("found in top comment by @alice on r/python").
"""

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A text chunk with character offsets into the original text.

    Section-aware fields are nullable so the legacy ``chunk_text()`` path
    keeps working unchanged. ``chunk_sections()`` populates them.
    """

    text: str
    char_start: int
    char_end: int
    token_count: int
    content_hash: str
    # ─── section provenance (Phase 1) ─────────────────────────────────
    section_id: str | None = None
    section_kind: str | None = None
    section_role: str | None = None
    heading_path: list[str] = field(default_factory=list)
    parent_section_id: str | None = None
    page_no: int | None = None
    timestamp_start_s: float | None = None
    author: str | None = None
    is_accepted_answer: bool = False


def _estimate_tokens(text: str) -> int:
    """Estimate token count from word count. ~1.3 tokens per word on average."""
    return max(1, int(len(text.split()) * 1.3))


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _split_on_paragraphs(text: str) -> list[tuple[str, int]]:
    """Split on double newlines, return (segment, char_start) pairs."""
    segments = []
    for match in re.finditer(r"(?:^|\n\n)(.+?)(?=\n\n|$)", text, re.DOTALL):
        segment = match.group(0).strip()
        if segment:
            start = match.start()
            # Adjust start to skip leading newlines
            while start < len(text) and text[start] == "\n":
                start += 1
            segments.append((segment, start))
    if not segments and text.strip():
        segments = [(text.strip(), text.index(text.strip()))]
    return segments


def _split_on_sentences(text: str) -> list[str]:
    """Split text on sentence boundaries."""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p for p in parts if p.strip()]


def chunk_text(
    text: str,
    target_tokens: int = 512,
    overlap_tokens: int = 64,
    max_chunks: int = 200,
) -> list[Chunk]:
    """Split text into overlapping chunks for retrieval.

    Strategy:
    1. Split on paragraph boundaries (\\n\\n)
    2. Accumulate paragraphs until target_tokens reached
    3. If a single paragraph exceeds target, split on sentences
    4. If a single sentence exceeds target, hard-split by words

    Returns list of Chunk with char offsets into the original text.
    """
    if not text or not text.strip():
        return []

    # Normalize whitespace but preserve structure
    cleaned = text.strip()
    if _estimate_tokens(cleaned) <= target_tokens:
        return [Chunk(
            text=cleaned,
            char_start=0,
            char_end=len(cleaned),
            token_count=_estimate_tokens(cleaned),
            content_hash=_content_hash(cleaned),
        )]

    # Split into paragraphs
    paragraphs = _split_on_paragraphs(cleaned)
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_tokens = 0
    chunk_char_start = paragraphs[0][1] if paragraphs else 0

    def _flush(parts: list[str], char_start: int) -> None:
        if not parts:
            return
        chunk_text_str = "\n\n".join(parts)
        char_end = char_start + len(chunk_text_str)
        # Clamp char_end to text length
        char_end = min(char_end, len(cleaned))
        chunks.append(Chunk(
            text=chunk_text_str,
            char_start=char_start,
            char_end=char_end,
            token_count=_estimate_tokens(chunk_text_str),
            content_hash=_content_hash(chunk_text_str),
        ))

    for para_text, para_start in paragraphs:
        para_tokens = _estimate_tokens(para_text)

        # Single paragraph exceeds target — split it further
        if para_tokens > target_tokens:
            # Flush current buffer first
            _flush(current_parts, chunk_char_start)
            current_parts = []
            current_tokens = 0

            # Split paragraph on sentences
            sentences = _split_on_sentences(para_text)
            sent_parts: list[str] = []
            sent_tokens = 0
            sent_start = para_start

            sent_cursor = 0  # tracks position within para_text for correct offsets
            for sent in sentences:
                sent_tok = _estimate_tokens(sent)
                if sent_tok > target_tokens:
                    # Hard-split long sentence by words
                    _flush(sent_parts, sent_start)
                    sent_parts = []
                    sent_tokens = 0
                    words = sent.split()
                    word_buf: list[str] = []
                    word_tok = 0
                    found = para_text.find(sent, sent_cursor)
                    ws = para_start + (found if found >= 0 else 0)
                    sent_cursor = found + len(sent) if found >= 0 else sent_cursor
                    for w in words:
                        wt = _estimate_tokens(w)
                        if word_tok + wt > target_tokens and word_buf:
                            chunk_str = " ".join(word_buf)
                            chunks.append(Chunk(
                                text=chunk_str,
                                char_start=ws,
                                char_end=min(ws + len(chunk_str), len(cleaned)),
                                token_count=_estimate_tokens(chunk_str),
                                content_hash=_content_hash(chunk_str),
                            ))
                            # Overlap: keep last few words
                            overlap_words = max(1, overlap_tokens // 2)
                            word_buf = word_buf[-overlap_words:]
                            word_tok = sum(_estimate_tokens(x) for x in word_buf)
                            ws = ws + len(chunk_str) - len(" ".join(word_buf))
                        word_buf.append(w)
                        word_tok += wt
                    if word_buf:
                        sent_parts = [" ".join(word_buf)]
                        sent_tokens = word_tok
                        sent_start = ws
                elif sent_tokens + sent_tok > target_tokens and sent_parts:
                    _flush(sent_parts, sent_start)
                    # Overlap: keep last sentence
                    if overlap_tokens > 0 and sent_parts:
                        last = sent_parts[-1]
                        if _estimate_tokens(last) <= overlap_tokens:
                            sent_parts = [last]
                            sent_tokens = _estimate_tokens(last)
                        else:
                            sent_parts = []
                            sent_tokens = 0
                    else:
                        sent_parts = []
                        sent_tokens = 0
                    found_s = para_text.find(sent, sent_cursor)
                    sent_start = para_start + (found_s if found_s >= 0 else 0)
                    sent_cursor = found_s + len(sent) if found_s >= 0 else sent_cursor
                    sent_parts.append(sent)
                    sent_tokens += sent_tok
                else:
                    if not sent_parts:
                        found_s = para_text.find(sent, sent_cursor)
                        sent_start = para_start + (found_s if found_s >= 0 else 0)
                        sent_cursor = found_s + len(sent) if found_s >= 0 else sent_cursor
                    else:
                        found_s = para_text.find(sent, sent_cursor)
                        if found_s >= 0:
                            sent_cursor = found_s + len(sent)
                    sent_parts.append(sent)
                    sent_tokens += sent_tok

            if sent_parts:
                _flush(sent_parts, sent_start)
                sent_parts = []

            # Reset for next paragraph
            chunk_char_start = para_start + len(para_text)
            continue

        # Normal case: paragraph fits within budget
        if current_tokens + para_tokens > target_tokens and current_parts:
            _flush(current_parts, chunk_char_start)
            # Overlap: keep last paragraph if small enough
            if overlap_tokens > 0 and current_parts:
                last = current_parts[-1]
                if _estimate_tokens(last) <= overlap_tokens:
                    current_parts = [last]
                    current_tokens = _estimate_tokens(last)
                    # Approximate char_start of overlap
                    chunk_char_start = para_start - len(last) - 2
                    chunk_char_start = max(0, chunk_char_start)
                else:
                    current_parts = []
                    current_tokens = 0
                    chunk_char_start = para_start
            else:
                current_parts = []
                current_tokens = 0
                chunk_char_start = para_start

        if not current_parts:
            chunk_char_start = para_start
        current_parts.append(para_text)
        current_tokens += para_tokens

    # Flush remainder
    _flush(current_parts, chunk_char_start)

    # Enforce max chunks limit
    return chunks[:max_chunks]


# ─── Section-aware chunking (Phase 1) ─────────────────────────────────

_HEADING_KINDS = frozenset({"title", "heading", "subtitle", "chapter"})


def _heading_path_for(sections, target_index: int) -> list[str]:
    """Walk backwards from ``target_index`` collecting ancestor heading text.

    Headings are sections with kind in {"title", "heading", "subtitle",
    "chapter"}; deeper-level headings replace shallower ones in the path
    once we cross their boundary. We walk in reverse from the target so
    the most recent heading at each depth wins.
    """
    path_by_depth: dict[int, str] = {}
    for s in sections[:target_index][::-1]:
        if s.kind in _HEADING_KINDS and s.text:
            d = s.depth or 0
            # First time we see a depth, take it; deeper depths first if
            # we want full breadcrumb back to the title. Use min-depth-wins.
            if d not in path_by_depth:
                path_by_depth[d] = s.text.strip()
        # Stop once we hit the page break before the section — keeps
        # heading_path scoped to the current page when sections come from PDF.
        if s.kind == "page_number":
            break
    return [path_by_depth[d] for d in sorted(path_by_depth)]


def chunk_sections(
    sections,
    target_tokens: int = 512,
    overlap_tokens: int = 64,
    max_chunks: int = 200,
) -> list[Chunk]:
    """Chunk a section list while preserving per-section metadata.

    Strategy:
      * Each section is chunked independently — never merge text across
        section boundaries (a comment and the next post should not share a
        chunk; their semantics differ).
      * Within a long section we still use the existing paragraph/sentence
        splitter for sane sub-chunks.
      * Skip ``boilerplate``/``promotional`` sections — they pollute search.
      * Each emitted chunk inherits the section's id/kind/role/author plus
        the heading_path computed from prior heading sections.
    """
    if not sections:
        return []

    chunks: list[Chunk] = []
    chunk_order = 0

    for idx, sec in enumerate(sections):
        text = (sec.text or "").strip()
        if not text:
            continue
        if sec.role in ("boilerplate", "promotional"):
            # Allow callers to opt back in by setting role="supplemental"
            # on, e.g., a video description they want indexed.
            continue

        # Use the section text directly for chunking. For very small
        # sections (single comment, single transcript line) the existing
        # ``chunk_text`` returns one chunk; for long ones it sub-splits.
        sub_chunks = chunk_text(
            text,
            target_tokens=target_tokens,
            overlap_tokens=overlap_tokens,
            max_chunks=max_chunks,
        )

        heading_path = _heading_path_for(sections, idx)

        for sub in sub_chunks:
            chunks.append(Chunk(
                text=sub.text,
                char_start=sub.char_start,
                char_end=sub.char_end,
                token_count=sub.token_count,
                content_hash=sub.content_hash,
                section_id=sec.id,
                section_kind=sec.kind,
                section_role=sec.role,
                heading_path=list(heading_path),
                parent_section_id=sec.parent_id,
                page_no=sec.page_no,
                timestamp_start_s=sec.timestamp_start_s,
                author=sec.author,
                is_accepted_answer=sec.is_accepted or sec.kind == "accepted_answer",
            ))
            chunk_order += 1
            if chunk_order >= max_chunks:
                return chunks

    return chunks


def contextualize(chunk: Chunk) -> str:
    """Prefix a chunk's text with its heading breadcrumb.

    Used by the embedder so a chunk like "Activations are squashed via..."
    becomes "Neural Networks > Layers > Activations are squashed via..."
    before being embedded, which dramatically improves retrieval on
    deeply-nested content. The stored chunk text stays unchanged — only
    the *embedding input* is contextualized.
    """
    if not chunk.heading_path:
        return chunk.text
    breadcrumb = " > ".join(chunk.heading_path)
    return f"{breadcrumb}\n\n{chunk.text}"
