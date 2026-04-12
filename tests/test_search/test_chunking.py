"""Tests for the text chunking module."""

from fourdpocket.search.chunking import Chunk, chunk_text


class TestChunkText:
    def test_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []
        assert chunk_text(None) == []  # type: ignore[arg-type]

    def test_short_text_single_chunk(self):
        text = "Hello world, this is a short text."
        chunks = chunk_text(text, target_tokens=512)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].char_start == 0
        assert chunks[0].char_end == len(text)
        assert chunks[0].token_count > 0
        assert len(chunks[0].content_hash) == 16

    def test_multi_paragraph_splits(self):
        paragraphs = ["Paragraph number %d with enough words to be meaningful." % i for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, target_tokens=30, overlap_tokens=0)
        assert len(chunks) > 1
        # All chunks should have valid offsets
        for c in chunks:
            assert c.char_start >= 0
            assert c.char_end > c.char_start
            assert c.token_count > 0

    def test_single_very_long_paragraph(self):
        """A single paragraph with no newlines should still get split."""
        words = ["word"] * 2000
        text = " ".join(words)
        chunks = chunk_text(text, target_tokens=100, overlap_tokens=10)
        assert len(chunks) > 1

    def test_max_chunks_limit(self):
        words = ["word"] * 5000
        text = " ".join(words)
        chunks = chunk_text(text, target_tokens=50, overlap_tokens=0, max_chunks=5)
        assert len(chunks) <= 5

    def test_chunk_is_dataclass(self):
        chunks = chunk_text("Some text here.")
        assert len(chunks) == 1
        c = chunks[0]
        assert isinstance(c, Chunk)
        assert isinstance(c.text, str)
        assert isinstance(c.char_start, int)
        assert isinstance(c.char_end, int)
        assert isinstance(c.token_count, int)
        assert isinstance(c.content_hash, str)

    def test_content_hash_deterministic(self):
        text = "Deterministic hashing test."
        c1 = chunk_text(text)[0]
        c2 = chunk_text(text)[0]
        assert c1.content_hash == c2.content_hash

    def test_content_hash_differs_for_different_text(self):
        c1 = chunk_text("First text.")[0]
        c2 = chunk_text("Second text.")[0]
        assert c1.content_hash != c2.content_hash

    def test_overlap_produces_more_chunks(self):
        paragraphs = ["Paragraph %d has some content here for testing." % i for i in range(10)]
        text = "\n\n".join(paragraphs)
        no_overlap = chunk_text(text, target_tokens=40, overlap_tokens=0)
        with_overlap = chunk_text(text, target_tokens=40, overlap_tokens=10)
        # With overlap there should be >= as many chunks
        assert len(with_overlap) >= len(no_overlap)

    def test_whitespace_only_paragraphs_skipped(self):
        text = "Real content here.\n\n   \n\n\n\nMore real content."
        chunks = chunk_text(text, target_tokens=512)
        assert len(chunks) >= 1
        for c in chunks:
            assert c.text.strip()  # no empty chunks

    def test_html_like_content(self):
        text = "<p>This is paragraph one.</p>\n\n<p>This is paragraph two with more words to fill space.</p>"
        chunks = chunk_text(text, target_tokens=512)
        assert len(chunks) >= 1
