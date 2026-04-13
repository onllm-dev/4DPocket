"""Tests for SqliteFtsBackend — wraps sqlite_fts with chunk-level fallback."""

import uuid

import pytest
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.search.backends.sqlite_fts_backend import SqliteFtsBackend
from fourdpocket.search.base import SearchFilters
from fourdpocket.search.sqlite_fts import index_item


@pytest.fixture
def search_user(db: Session):
    user = User(
        email="ftsuser@example.com",
        username="ftsuser",
        password_hash="$2b$12$fakehash",
        display_name="FTS Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def search_item(db: Session, search_user):
    item = KnowledgeItem(
        user_id=search_user.id,
        title="Python Async Tutorial",
        content="Learn async programming in Python with asyncio and await keywords.",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    index_item(db, item)
    return item


class TestSqliteFtsBackend:
    def test_index_item(self, db: Session, search_user, search_item):
        backend = SqliteFtsBackend()
        backend.init(db)

        # Re-index should update the existing entry
        backend.index_item(db, search_item)

        results = backend.search(
            db, "async", search_user.id,
            SearchFilters(), limit=20, offset=0,
        )
        assert len(results) >= 1
        assert results[0].item_id == str(search_item.id)

    def test_search_returns_keyword_hits(self, db: Session, search_user, search_item):
        backend = SqliteFtsBackend()
        backend.init(db)

        results = backend.search(
            db, "Python", search_user.id,
            SearchFilters(), limit=20, offset=0,
        )
        assert len(results) >= 1
        hit = results[0]
        assert hit.item_id == str(search_item.id)
        assert isinstance(hit.rank, float)

    def test_search_no_match(self, db: Session, search_user, search_item):
        backend = SqliteFtsBackend()
        backend.init(db)

        results = backend.search(
            db, "zzznomatchxxx", search_user.id,
            SearchFilters(), limit=20, offset=0,
        )
        assert len(results) == 0

    def test_search_with_item_type_filter(self, db: Session, search_user):
        item = KnowledgeItem(
            user_id=search_user.id,
            title="Rust Error Handling",
            content="Result and Option types for error handling.",
            item_type="note",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        index_item(db, item)

        backend = SqliteFtsBackend()
        backend.init(db)

        results = backend.search(
            db, "error", search_user.id,
            SearchFilters(item_type="note"), limit=20, offset=0,
        )
        assert len(results) >= 1
        assert all(r.item_id == str(item.id) for r in results)

    def test_search_with_source_platform_filter(self, db: Session, search_user):
        item = KnowledgeItem(
            user_id=search_user.id,
            title="YouTube Video",
            content="This video is from YouTube about Python programming.",
            source_platform="youtube",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        index_item(db, item)

        backend = SqliteFtsBackend()
        backend.init(db)

        results = backend.search(
            db, "Python", search_user.id,
            SearchFilters(source_platform="youtube"), limit=20, offset=0,
        )
        assert len(results) >= 1

    def test_search_empty_query(self, db: Session, search_user, search_item):
        backend = SqliteFtsBackend()
        backend.init(db)

        results = backend.search(
            db, "", search_user.id,
            SearchFilters(), limit=20, offset=0,
        )
        # Empty query returns empty
        assert results == []

    def test_delete_item(self, db: Session, search_user, search_item):
        backend = SqliteFtsBackend()
        backend.init(db)

        backend.delete_item(db, search_item.id)

        results = backend.search(
            db, "Python", search_user.id,
            SearchFilters(), limit=20, offset=0,
        )
        assert all(r.item_id != str(search_item.id) for r in results)

    def test_index_chunks(self, db: Session, search_user, search_item):
        backend = SqliteFtsBackend()
        backend.init(db)

        class FakeChunk:
            id = uuid.uuid4()
            text = "First chunk about async programming"
            chunk_order = 0

        backend.index_chunks(
            db, search_item.id, search_user.id,
            [FakeChunk()], "Python Async Tutorial", "https://example.com",
        )

        results = backend.search(
            db, "async", search_user.id,
            SearchFilters(), limit=20, offset=0,
        )
        assert len(results) >= 1

    def test_search_pagination_offset(self, db: Session, search_user):
        """Test offset pagination returns correct windows."""
        backend = SqliteFtsBackend()
        backend.init(db)

        # Create multiple items
        for i in range(5):
            item = KnowledgeItem(
                user_id=search_user.id,
                title=f"Item Title {i}",
                content=f"Content for item {i} with searchable term",
            )
            db.add(item)
        db.commit()

        # Re-index all
        from sqlmodel import select
        all_items = db.exec(
            select(KnowledgeItem).where(KnowledgeItem.user_id == search_user.id)
        ).all()
        for item in all_items:
            index_item(db, item)

        results_page1 = backend.search(
            db, "searchable", search_user.id,
            SearchFilters(), limit=2, offset=0,
        )
        results_page2 = backend.search(
            db, "searchable", search_user.id,
            SearchFilters(), limit=2, offset=2,
        )

        # Pages should not overlap
        page1_ids = {r.item_id for r in results_page1}
        page2_ids = {r.item_id for r in results_page2}
        assert page1_ids.isdisjoint(page2_ids)


class TestSqliteFtsBackendErrors:
    def test_search_handles_invalid_query_chars(self, db: Session, search_user, search_item):
        """Special FTS5 characters are sanitized and don't raise."""
        backend = SqliteFtsBackend()
        backend.init(db)

        # These patterns would break raw FTS5 query but should be handled gracefully
        results = backend.search(
            db, 'test "query * AND OR NOT', search_user.id,
            SearchFilters(), limit=20, offset=0,
        )
        # Should return empty or results, not raise
        assert isinstance(results, list)

    def test_search_with_tag_filter(self, db: Session, search_user):
        """Tag filter should be passed through even if tags are empty."""
        backend = SqliteFtsBackend()
        backend.init(db)

        # No items with tags, but filter syntax is valid
        results = backend.search(
            db, "python", search_user.id,
            SearchFilters(tags=["nonexistent"]), limit=20, offset=0,
        )
        assert results == []
