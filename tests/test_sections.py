"""Tests for the structured-sections schema + section-aware chunking."""

import pytest

from fourdpocket.processors.sections import (
    Section,
    make_section_id,
    section_summary_for_metadata,
    sections_to_text,
)
from fourdpocket.search.chunking import chunk_sections, chunk_text, contextualize

# ─── Section dataclass + helpers ─────────────────────────────────


def test_make_section_id_is_stable():
    a = make_section_id("https://example.com", 0)
    b = make_section_id("https://example.com", 0)
    assert a == b
    assert len(a) == 12


def test_make_section_id_changes_with_order():
    assert make_section_id("seed", 0) != make_section_id("seed", 1)


def test_section_is_frozen():
    s = Section(id="s1", kind="paragraph", text="hi")
    with pytest.raises((AttributeError, Exception)):
        s.text = "mutated"  # type: ignore


# ─── sections_to_text ──────────────────────────────────────────


def test_sections_to_text_skips_boilerplate_and_promo():
    sections = [
        Section(id="1", kind="paragraph", text="real content"),
        Section(id="2", kind="paragraph", text="ad", role="promotional"),
        Section(id="3", kind="paragraph", text="footer", role="boilerplate"),
        Section(id="4", kind="paragraph", text="more real"),
    ]
    out = sections_to_text(sections)
    assert "real content" in out
    assert "ad" not in out
    assert "footer" not in out
    assert "more real" in out


def test_sections_to_text_renders_headings_with_level():
    sections = [
        Section(id="1", kind="title", text="Doc Title"),
        Section(id="2", kind="heading", depth=0, text="H1"),
        Section(id="3", kind="heading", depth=1, text="H2"),
        Section(id="4", kind="paragraph", text="Body"),
    ]
    out = sections_to_text(sections)
    assert "# Doc Title" in out
    assert "# H1" in out
    assert "## H2" in out
    assert "Body" in out


def test_sections_to_text_renders_threaded_comments():
    sections = [
        Section(id="1", kind="post", author="op", score=10, text="What is X?"),
        Section(id="2", kind="comment", parent_id="1", depth=1,
                author="alice", score=5, text="X is Y"),
        Section(id="3", kind="reply", parent_id="2", depth=2,
                author="bob", score=2, text="Actually Z"),
    ]
    out = sections_to_text(sections)
    assert "@op (10): What is X?" in out
    assert "@alice (5): X is Y" in out
    assert "@bob (2): Actually Z" in out


def test_sections_to_text_renders_code_with_language():
    sections = [
        Section(id="1", kind="code", text="print('hi')", extra={"language": "python"}),
    ]
    out = sections_to_text(sections)
    assert "```python" in out
    assert "print('hi')" in out


def test_sections_to_text_handles_transcript_timestamps():
    sections = [
        Section(id="1", kind="transcript_segment", text="hello world",
                timestamp_start_s=12.5),
    ]
    out = sections_to_text(sections)
    assert "[12s] hello world" in out


def test_section_summary_counts():
    sections = [
        Section(id="1", kind="post", role="main", text="x"),
        Section(id="2", kind="comment", role="main", text="y"),
        Section(id="3", kind="comment", role="main", text="z"),
        Section(id="4", kind="paragraph", role="boilerplate", text="w"),
    ]
    summary = section_summary_for_metadata(sections)
    assert summary["section_counts"] == {"post": 1, "comment": 2, "paragraph": 1}
    assert summary["role_counts"] == {"main": 3, "boilerplate": 1}


# ─── chunk_sections ───────────────────────────────────────────


def test_chunk_sections_returns_one_chunk_per_short_section():
    sections = [
        Section(id="a", kind="post", order=0, role="main", text="post body", author="op"),
        Section(id="b", kind="comment", order=1, parent_id="a", depth=1,
                role="main", text="comment body", author="alice"),
    ]
    chunks = chunk_sections(sections)
    assert len(chunks) == 2
    assert chunks[0].section_id == "a"
    assert chunks[0].section_kind == "post"
    assert chunks[0].author == "op"
    assert chunks[1].section_id == "b"
    assert chunks[1].section_kind == "comment"
    assert chunks[1].parent_section_id == "a"
    assert chunks[1].author == "alice"


def test_chunk_sections_skips_boilerplate():
    sections = [
        Section(id="a", kind="paragraph", text="real", role="main"),
        Section(id="b", kind="footer", text="© 2026 footer", role="boilerplate"),
    ]
    chunks = chunk_sections(sections)
    assert len(chunks) == 1
    assert chunks[0].section_id == "a"


def test_chunk_sections_propagates_heading_path():
    sections = [
        Section(id="t", kind="title", order=0, text="Doc Title"),
        Section(id="h", kind="heading", order=1, depth=1, text="Chapter 1"),
        Section(id="p", kind="paragraph", order=2, text="The actual content."),
    ]
    chunks = chunk_sections(sections)
    body = next(c for c in chunks if c.section_id == "p")
    assert "Doc Title" in body.heading_path
    assert "Chapter 1" in body.heading_path


def test_chunk_sections_subsplits_long_section():
    long_text = " ".join(["word"] * 5000)  # vastly exceeds 512 tokens
    sections = [Section(id="big", kind="paragraph", order=0, text=long_text)]
    chunks = chunk_sections(sections, target_tokens=128, overlap_tokens=16)
    assert len(chunks) > 1
    # All sub-chunks share the section_id
    assert all(c.section_id == "big" for c in chunks)


def test_chunk_sections_preserves_video_timestamps():
    sections = [
        Section(id="seg1", kind="transcript_segment", order=0, text="hello",
                timestamp_start_s=0.0),
        Section(id="seg2", kind="transcript_segment", order=1, text="world",
                timestamp_start_s=12.5),
    ]
    chunks = chunk_sections(sections)
    assert chunks[0].timestamp_start_s == 0.0
    assert chunks[1].timestamp_start_s == 12.5


def test_chunk_sections_marks_accepted_answer():
    sections = [
        Section(id="q", kind="question", order=0, text="How do I X?"),
        Section(id="a1", kind="accepted_answer", order=1, text="Do Y", is_accepted=True),
        Section(id="a2", kind="answer", order=2, text="Or Z"),
    ]
    chunks = chunk_sections(sections)
    accepted = next(c for c in chunks if c.section_id == "a1")
    other = next(c for c in chunks if c.section_id == "a2")
    assert accepted.is_accepted_answer is True
    assert other.is_accepted_answer is False


def test_chunk_sections_respects_max_chunks():
    sections = [
        Section(id=f"s{i}", kind="paragraph", order=i, text=f"text {i}")
        for i in range(50)
    ]
    chunks = chunk_sections(sections, max_chunks=10)
    assert len(chunks) <= 10


def test_chunk_sections_empty_returns_empty():
    assert chunk_sections([]) == []
    assert chunk_sections([Section(id="x", kind="paragraph", text="")]) == []


# ─── contextualize ────────────────────────────────────────────


def test_contextualize_prefixes_breadcrumb():
    from fourdpocket.search.chunking import Chunk
    c = Chunk(
        text="Body text",
        char_start=0, char_end=9, token_count=2, content_hash="x",
        heading_path=["Doc", "Chapter 1"],
    )
    out = contextualize(c)
    assert out.startswith("Doc > Chapter 1")
    assert "Body text" in out


def test_contextualize_no_breadcrumb_passthrough():
    from fourdpocket.search.chunking import Chunk
    c = Chunk(text="Just text", char_start=0, char_end=9, token_count=2, content_hash="x")
    assert contextualize(c) == "Just text"


# ─── back-compat: chunk_text path still works ────────────────


def test_legacy_chunk_text_unchanged():
    chunks = chunk_text("para one.\n\npara two.\n\npara three.")
    assert len(chunks) >= 1
    # Section fields default to None
    assert chunks[0].section_id is None
    assert chunks[0].section_kind is None
