"""Integration tests for chunk-level FTS5 indexing and search."""

import uuid

import pytest
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.item_chunk import ItemChunk
from fourdpocket.models.user import User
from fourdpocket.search.chunking import chunk_text
from fourdpocket.search.sqlite_fts import (
    delete_chunks,
    index_chunks,
    search_chunks,
)


@pytest.fixture
def user_and_item(db: Session):
    """Create a test user and item for chunk tests."""
    user = User(
        email="chunktest@example.com",
        username="chunkuser",
        password_hash="$2b$12$fakehash",
        display_name="Chunk Test User",
    )
    db.add(user)
    db.flush()

    item = KnowledgeItem(
        user_id=user.id,
        title="Understanding RAG Pipelines",
        url="https://example.com/rag",
        content=(
            "Retrieval Augmented Generation combines retrieval with language models. "
            "It works by first finding relevant documents using vector search.\n\n"
            "The retrieved documents are then passed as context to the language model. "
            "This approach significantly improves factual accuracy.\n\n"
            "Popular frameworks for building RAG include LangChain, LlamaIndex, and Haystack. "
            "Each has different strengths and trade-offs for production use."
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(user)
    db.refresh(item)
    return user, item


class TestChunkIndexing:
    def test_chunk_and_index(self, db: Session, user_and_item):
        user, item = user_and_item

        # Chunk the content
        chunks = chunk_text(item.content, target_tokens=30, overlap_tokens=0)
        assert len(chunks) >= 1

        # Create ItemChunk models
        chunk_models = []
        for i, c in enumerate(chunks):
            cm = ItemChunk(
                item_id=item.id,
                user_id=user.id,
                chunk_order=i,
                text=c.text,
                token_count=c.token_count,
                char_start=c.char_start,
                char_end=c.char_end,
                content_hash=c.content_hash,
            )
            db.add(cm)
            chunk_models.append(cm)
        db.commit()

        # Index chunks into FTS5
        index_chunks(db, item.id, user.id, chunk_models, item.title, item.url)

        # Search should find the item via chunk content
        results = search_chunks(db, "vector search", user.id)
        assert len(results) >= 1
        assert results[0]["item_id"] == str(item.id)

    def test_search_chunks_returns_correct_shape(self, db: Session, user_and_item):
        user, item = user_and_item

        chunks = chunk_text(item.content, target_tokens=50, overlap_tokens=0)
        chunk_models = []
        for i, c in enumerate(chunks):
            cm = ItemChunk(
                item_id=item.id,
                user_id=user.id,
                chunk_order=i,
                text=c.text,
                token_count=c.token_count,
                char_start=c.char_start,
                char_end=c.char_end,
                content_hash=c.content_hash,
            )
            db.add(cm)
            chunk_models.append(cm)
        db.commit()

        index_chunks(db, item.id, user.id, chunk_models, item.title, item.url)

        results = search_chunks(db, "RAG", user.id)
        assert len(results) >= 1
        result = results[0]
        # Must have the same keys as item-level search
        assert "item_id" in result
        assert "rank" in result
        assert "title_snippet" in result
        assert "content_snippet" in result

    def test_delete_chunks_removes_fts_entries(self, db: Session, user_and_item):
        user, item = user_and_item

        chunks = chunk_text(item.content, target_tokens=50, overlap_tokens=0)
        chunk_models = []
        for i, c in enumerate(chunks):
            cm = ItemChunk(
                item_id=item.id,
                user_id=user.id,
                chunk_order=i,
                text=c.text,
                token_count=c.token_count,
                char_start=c.char_start,
                char_end=c.char_end,
                content_hash=c.content_hash,
            )
            db.add(cm)
            chunk_models.append(cm)
        db.commit()

        index_chunks(db, item.id, user.id, chunk_models, item.title, item.url)

        # Verify search works first
        results = search_chunks(db, "RAG", user.id)
        assert len(results) >= 1

        # Delete and verify empty
        delete_chunks(db, item.id)
        results = search_chunks(db, "RAG", user.id)
        assert len(results) == 0

    def test_user_scoping(self, db: Session, user_and_item):
        user, item = user_and_item

        chunks = chunk_text(item.content, target_tokens=100, overlap_tokens=0)
        chunk_models = []
        for i, c in enumerate(chunks):
            cm = ItemChunk(
                item_id=item.id,
                user_id=user.id,
                chunk_order=i,
                text=c.text,
                token_count=c.token_count,
                char_start=c.char_start,
                char_end=c.char_end,
                content_hash=c.content_hash,
            )
            db.add(cm)
            chunk_models.append(cm)
        db.commit()

        index_chunks(db, item.id, user.id, chunk_models, item.title, item.url)

        # Different user should see no results
        other_user_id = uuid.uuid4()
        results = search_chunks(db, "RAG", other_user_id)
        assert len(results) == 0

    def test_rollup_best_chunk_per_item(self, db: Session, user_and_item):
        """Multiple chunks for one item should produce exactly one result (best chunk)."""
        user, item = user_and_item

        chunks = chunk_text(item.content, target_tokens=20, overlap_tokens=0)
        chunk_models = []
        for i, c in enumerate(chunks):
            cm = ItemChunk(
                item_id=item.id,
                user_id=user.id,
                chunk_order=i,
                text=c.text,
                token_count=c.token_count,
                char_start=c.char_start,
                char_end=c.char_end,
                content_hash=c.content_hash,
            )
            db.add(cm)
            chunk_models.append(cm)
        db.commit()

        assert len(chunk_models) > 1, "Need multiple chunks to test rollup"
        index_chunks(db, item.id, user.id, chunk_models, item.title, item.url)

        results = search_chunks(db, "language model", user.id)
        # Should have at most 1 result per item (rolled up)
        item_ids = [r["item_id"] for r in results]
        assert len(item_ids) == len(set(item_ids)), "Duplicates found — rollup broken"
