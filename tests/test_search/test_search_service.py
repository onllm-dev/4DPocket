"""Tests for SearchService and backend abstraction."""


import pytest
from sqlmodel import Session

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User
from fourdpocket.search.base import KeywordHit, SearchFilters, SearchResult, VectorHit
from fourdpocket.search.reranker import NullReranker
from fourdpocket.search.service import SearchService
from fourdpocket.search.sqlite_fts import index_item


@pytest.fixture
def search_user(db: Session):
    user = User(
        email="searchtest@example.com",
        username="searchuser",
        password_hash="$2b$12$fakehash",
        display_name="Search Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def search_items(db: Session, search_user):
    """Create 3 items with distinct content for search testing."""
    items = []
    contents = [
        ("Python FastAPI Tutorial", "FastAPI is a modern web framework for building APIs with Python."),
        ("Rust Memory Safety", "Rust provides memory safety without garbage collection through ownership."),
        ("Docker Containers Guide", "Docker containers package applications with their dependencies."),
    ]
    for title, content in contents:
        item = KnowledgeItem(
            user_id=search_user.id,
            title=title,
            content=content,
        )
        db.add(item)
        items.append(item)
    db.commit()
    for item in items:
        db.refresh(item)
        index_item(db, item)
    return items


class TestSearchService:
    def test_keyword_only_search(self, db: Session, search_user, search_items):
        """SearchService returns results from keyword backend."""
        from fourdpocket.search.backends.sqlite_fts_backend import SqliteFtsBackend

        # Minimal vector backend that returns nothing
        class NoOpVector:
            def upsert_item(self, *a, **kw): pass
            def upsert_chunk(self, *a, **kw): pass
            def delete_item(self, *a, **kw): pass
            def search(self, *a, **kw): return []

        service = SearchService(
            keyword=SqliteFtsBackend(),
            vector=NoOpVector(),
            reranker=NullReranker(),
        )

        results = service.search(db, "FastAPI", search_user.id)
        assert len(results) >= 1
        assert any("Python" in (r.title_snippet or "") or r.item_id == str(search_items[0].id)
                    for r in results)

    def test_search_returns_search_result_type(self, db: Session, search_user, search_items):
        from fourdpocket.search.backends.sqlite_fts_backend import SqliteFtsBackend

        class NoOpVector:
            def upsert_item(self, *a, **kw): pass
            def upsert_chunk(self, *a, **kw): pass
            def delete_item(self, *a, **kw): pass
            def search(self, *a, **kw): return []

        service = SearchService(
            keyword=SqliteFtsBackend(),
            vector=NoOpVector(),
            reranker=NullReranker(),
        )

        results = service.search(db, "Rust", search_user.id)
        assert len(results) >= 1
        r = results[0]
        assert isinstance(r, SearchResult)
        assert r.item_id
        assert isinstance(r.score, float)
        assert isinstance(r.sources, list)

    def test_search_with_filters(self, db: Session, search_user, search_items):
        from fourdpocket.search.backends.sqlite_fts_backend import SqliteFtsBackend

        class NoOpVector:
            def upsert_item(self, *a, **kw): pass
            def upsert_chunk(self, *a, **kw): pass
            def delete_item(self, *a, **kw): pass
            def search(self, *a, **kw): return []

        service = SearchService(
            keyword=SqliteFtsBackend(),
            vector=NoOpVector(),
            reranker=NullReranker(),
        )

        filters = SearchFilters(is_favorite=True)
        results = service.search(db, "Docker", search_user.id, filters=filters)
        # None are favorited, so should return empty
        assert len(results) == 0

    def test_index_item(self, db: Session, search_user):
        from fourdpocket.search.backends.sqlite_fts_backend import SqliteFtsBackend

        class NoOpVector:
            def upsert_item(self, *a, **kw): pass
            def upsert_chunk(self, *a, **kw): pass
            def delete_item(self, *a, **kw): pass
            def search(self, *a, **kw): return []

        service = SearchService(
            keyword=SqliteFtsBackend(),
            vector=NoOpVector(),
            reranker=NullReranker(),
        )

        item = KnowledgeItem(
            user_id=search_user.id,
            title="Service Index Test",
            content="Unique service test content for indexing.",
        )
        db.add(item)
        db.commit()

        service.index_item(db, item)
        results = service.search(db, "Unique service test", search_user.id)
        assert len(results) >= 1

    def test_rrf_fusion(self, db: Session, search_user):
        from fourdpocket.search.backends.sqlite_fts_backend import SqliteFtsBackend

        class NoOpVector:
            def upsert_item(self, *a, **kw): pass
            def upsert_chunk(self, *a, **kw): pass
            def delete_item(self, *a, **kw): pass
            def search(self, *a, **kw): return []

        service = SearchService(
            keyword=SqliteFtsBackend(),
            vector=NoOpVector(),
            reranker=NullReranker(),
        )

        kw_hits = [
            KeywordHit(item_id="aaa", rank=-1.0, title_snippet="A"),
            KeywordHit(item_id="bbb", rank=-0.5, title_snippet="B"),
        ]
        vec_hits = [
            VectorHit(item_id="bbb", similarity=0.9),
            VectorHit(item_id="ccc", similarity=0.8),
        ]

        results = service._rrf_fusion(kw_hits, vec_hits)
        ids = [r.item_id for r in results]
        # bbb appears in both lists, should rank highest
        assert ids[0] == "bbb"
        assert len(results) == 3


class TestNullReranker:
    def test_passthrough(self):
        reranker = NullReranker()
        result = reranker.rerank("query", ["doc1", "doc2", "doc3"], top_k=2)
        assert len(result) == 2
        assert result[0] == (0, 1.0)
        assert result[1] == (1, 1.0)

    def test_empty_docs(self):
        reranker = NullReranker()
        result = reranker.rerank("query", [], top_k=5)
        assert result == []

    def test_top_k_larger_than_docs(self):
        reranker = NullReranker()
        result = reranker.rerank("query", ["doc1"], top_k=10)
        assert len(result) == 1


class TestSearchResult:
    def test_to_dict(self):
        r = SearchResult(
            item_id="abc",
            score=0.95,
            title_snippet="<mark>test</mark>",
            content_snippet="some content",
            sources=["fts", "semantic"],
        )
        d = r.to_dict()
        assert d["item_id"] == "abc"
        assert d["rank"] == 0.95
        assert d["title_snippet"] == "<mark>test</mark>"
        assert d["sources"] == ["fts", "semantic"]
