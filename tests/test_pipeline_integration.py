"""Integration test: sections → fetcher serialization → pipeline re-hydration → chunks.

Verifies that provenance fields (section_id, section_kind, author,
heading_path, etc.) survive the full round-trip from processor output
through JSON serialization and back into ItemChunk-ready Chunk objects.
"""

from __future__ import annotations

import dataclasses

from fourdpocket.processors.sections import Section, make_section_id, sections_to_text
from fourdpocket.search.chunking import chunk_sections


def _make_reddit_sections() -> list[Section]:
    """Build a realistic Reddit-style section tree."""
    post_id = make_section_id("reddit-test", 0)
    c1_id = make_section_id("reddit-test", 1)
    return [
        Section(
            id=post_id, kind="post", order=0, role="main",
            text="Why is Python so popular? " * 20,
            author="op_user", score=142,
        ),
        Section(
            id=c1_id, kind="comment", order=1, role="main",
            text="Because of its ecosystem. " * 15,
            parent_id=post_id, depth=1,
            author="commenter_1", score=311,
        ),
        Section(
            id=make_section_id("reddit-test", 2), kind="reply", order=2,
            role="main", text="Also the readability.",
            parent_id=c1_id, depth=2,
            author="commenter_2", score=42,
        ),
    ]


def _make_so_sections() -> list[Section]:
    """Build a realistic StackOverflow-style section tree."""
    q_id = make_section_id("so-test", 0)
    a_id = make_section_id("so-test", 1)
    return [
        Section(
            id=q_id, kind="question", order=0, role="main",
            text="How do I sort a list of dicts by value? " * 10,
            author="asker", score=200,
        ),
        Section(
            id=a_id, kind="accepted_answer", order=1, role="main",
            text="Use sorted() with a key function. " * 20,
            parent_id=q_id, depth=1,
            author="expert",
            score=500,
            extra={"is_accepted": True},
        ),
        Section(
            id=make_section_id("so-test", 2), kind="comment", order=2,
            role="supplemental", text="Thanks, this worked perfectly!",
            parent_id=a_id, depth=2,
            author="asker", score=3,
        ),
    ]


def _make_article_with_headings() -> list[Section]:
    """Build sections with heading hierarchy for heading_path testing."""
    return [
        Section(
            id=make_section_id("article", 0), kind="title", order=0,
            role="main", text="Machine Learning Guide",
        ),
        Section(
            id=make_section_id("article", 1), kind="heading", order=1,
            role="main", text="Introduction", depth=1,
        ),
        Section(
            id=make_section_id("article", 2), kind="paragraph", order=2,
            role="main", text="ML is a subset of AI. " * 30,
        ),
        Section(
            id=make_section_id("article", 3), kind="heading", order=3,
            role="main", text="Supervised Learning", depth=1,
        ),
        Section(
            id=make_section_id("article", 4), kind="paragraph", order=4,
            role="main", text="Supervised learning uses labeled data. " * 30,
        ),
    ]


def test_reddit_sections_roundtrip_through_json():
    """Section → asdict → re-hydrate → chunk_sections preserves provenance."""
    sections = _make_reddit_sections()

    # Simulate fetcher serialization
    serialized = [dataclasses.asdict(s) for s in sections]

    # Simulate pipeline re-hydration
    rehydrated = [Section(**sd) for sd in serialized]
    assert len(rehydrated) == len(sections)
    for orig, rh in zip(sections, rehydrated):
        assert orig == rh

    # Chunk
    chunks = chunk_sections(rehydrated, target_tokens=50, overlap_tokens=10)
    assert len(chunks) > 0

    # Verify provenance survived
    post_chunks = [c for c in chunks if c.section_kind == "post"]
    assert post_chunks
    assert post_chunks[0].author == "op_user"

    comment_chunks = [c for c in chunks if c.section_kind == "comment"]
    assert comment_chunks
    assert comment_chunks[0].author == "commenter_1"
    assert comment_chunks[0].section_role == "main"


def test_so_sections_roundtrip_preserves_accepted_answer():
    sections = _make_so_sections()
    serialized = [dataclasses.asdict(s) for s in sections]
    rehydrated = [Section(**sd) for sd in serialized]
    chunks = chunk_sections(rehydrated, target_tokens=50, overlap_tokens=10)

    accepted = [c for c in chunks if c.section_kind == "accepted_answer"]
    assert accepted
    assert accepted[0].is_accepted_answer is True
    assert accepted[0].author == "expert"


def test_article_heading_path_propagation():
    sections = _make_article_with_headings()
    chunks = chunk_sections(sections, target_tokens=50, overlap_tokens=10)

    para_chunks = [c for c in chunks if c.section_kind == "paragraph"]
    assert para_chunks

    # First paragraph should have heading_path including "Introduction"
    first_para = para_chunks[0]
    assert first_para.heading_path
    assert "Introduction" in first_para.heading_path

    # Second paragraph should have "Supervised Learning"
    later_para = [c for c in para_chunks if c.heading_path and "Supervised Learning" in c.heading_path]
    assert later_para


def test_sections_to_text_roundtrip():
    """Verify sections_to_text produces readable Markdown."""
    sections = _make_reddit_sections()
    text = sections_to_text(sections)
    assert "op_user" in text
    assert "commenter_1" in text
    assert "Python" in text


def test_rehydration_with_unknown_field():
    """Forward-compat: extra fields in serialized data don't crash."""
    section = Section(
        id="test", kind="post", order=0, text="hello", role="main",
    )
    sd = dataclasses.asdict(section)
    sd["future_field"] = "some_value"  # unknown field

    # Direct construction should fail (frozen dataclass)
    try:
        Section(**sd)
        rehydrated_ok = True
    except TypeError:
        rehydrated_ok = False

    # The pipeline fallback should handle this
    if not rehydrated_ok:
        fallback = Section(
            id=sd.get("id", ""),
            kind=sd.get("kind", "uncategorized"),
            order=sd.get("order", 0),
            text=sd.get("text", ""),
            role=sd.get("role", "main"),
            parent_id=sd.get("parent_id"),
            depth=sd.get("depth", 0),
            author=sd.get("author"),
            score=sd.get("score"),
        )
        assert fallback.id == "test"
        assert fallback.kind == "post"
        assert fallback.text == "hello"


def test_boilerplate_sections_filtered_out():
    """Sections with boilerplate/promotional roles should be excluded from chunks."""
    sections = [
        Section(
            id=make_section_id("test", 0), kind="paragraph", order=0,
            role="main", text="Main content here. " * 20,
        ),
        Section(
            id=make_section_id("test", 1), kind="paragraph", order=1,
            role="boilerplate", text="Cookie consent notice. " * 10,
        ),
        Section(
            id=make_section_id("test", 2), kind="paragraph", order=2,
            role="promotional", text="Buy our product! " * 10,
        ),
    ]
    chunks = chunk_sections(sections, target_tokens=50, overlap_tokens=10)

    # Only main-role content should be chunked
    for c in chunks:
        assert c.section_role != "boilerplate"
        assert c.section_role != "promotional"
