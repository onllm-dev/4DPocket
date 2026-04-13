"""Tests for SearchService and backend abstraction."""


import uuid
from unittest.mock import MagicMock

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


# === PHASE 1A MOPUP ADDITIONS ===

def _make_service(keyword, vector, reranker=None):
    """Create SearchService with real __init__ but bypassed external dependencies."""
    return SearchService(keyword=keyword, vector=vector, reranker=reranker)


class TestSearchServiceNew:
    """Additional SearchService tests — mocked backends."""

    def test_search_vector_path(self, db: Session, search_user, monkeypatch):
        """Vector search path — embed_single returns embedding, vector backend returns results."""
        from fourdpocket.search.base import SearchResult

        mock_vector = MagicMock()
        mock_vector.search.return_value = [
            SearchResult(item_id="abc", score=0.9, title_snippet="Title", content_snippet="Content", sources=["semantic"])
        ]
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = []

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.1] * 384

        monkeypatch.setattr("fourdpocket.ai.factory.get_embedding_provider", lambda: mock_provider)

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        results = service.search(db, "test query", user_id=search_user.id, filters=None, limit=20)
        assert len(results) == 1
        mock_provider.embed_single.assert_called_once_with("test query")
        mock_vector.search.assert_called_once()
        assert results[0].sources == ["semantic"]

    def test_search_empty_query_skips_vector(self, db: Session, search_user, monkeypatch):
        """Empty/whitespace-only query skips vector search."""
        mock_vector = MagicMock()
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = []

        monkeypatch.setattr("fourdpocket.ai.factory.get_embedding_provider", lambda: MagicMock())

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        results = service.search(db, "   ", user_id=search_user.id, filters=None, limit=20)
        assert results == []
        mock_vector.search.assert_not_called()

    def test_search_vector_embed_failure_is_graceful(self, db: Session, search_user, monkeypatch):
        """embed_single raises — vector path silently skipped."""
        mock_vector = MagicMock()
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = [KeywordHit(item_id="kw-only", rank=1.0, title_snippet="KW")]

        mock_provider = MagicMock()
        mock_provider.embed_single.side_effect = Exception("embedding failed")

        monkeypatch.setattr("fourdpocket.ai.factory.get_embedding_provider", lambda: mock_provider)

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        results = service.search(db, "test", user_id=search_user.id, filters=None, limit=20)
        assert len(results) == 1
        assert results[0].item_id == "kw-only"

    def test_search_reranker_skips_when_disabled(self, db: Session, search_user, monkeypatch):
        """Reranker not called when config enabled=False."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = [
            KeywordHit(item_id="item-1", rank=1.0, title_snippet="Title", content_snippet="Content"),
        ]

        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = None  # signals skip

        mock_settings = MagicMock()
        mock_settings.rerank.enabled = False

        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        service = _make_service(keyword=mock_keyword, vector=mock_vector, reranker=mock_reranker)
        results = service.search(db, "test", user_id=search_user.id, filters=None, limit=20)
        assert len(results) == 1
        mock_reranker.rerank.assert_not_called()

    def test_search_reranker_model_load_failure_skips(self, db: Session, search_user, monkeypatch):
        """Reranker returns None (load failed) — results keep RRF order."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = [
            KeywordHit(item_id="item-1", rank=1.0, title_snippet="First", content_snippet=""),
            KeywordHit(item_id="item-2", rank=1.0, title_snippet="Second", content_snippet=""),
        ]

        # Simulate reranker that failed to load model
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = None  # signals caller to skip

        mock_settings = MagicMock()
        mock_settings.rerank.enabled = True
        mock_settings.rerank.rerank = True
        mock_settings.rerank.top_k = 20
        mock_settings.rerank.candidate_pool = 50

        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        service = _make_service(keyword=mock_keyword, vector=mock_vector, reranker=mock_reranker)
        results = service.search(db, "test", user_id=search_user.id, filters=None, limit=20)
        # Results preserve RRF order since reranking was skipped
        assert results[0].item_id == "item-1"
        assert results[1].item_id == "item-2"

    def test_search_applies_offset_and_limit(self, db: Session, search_user, monkeypatch):
        """offset and limit are correctly sliced from merged results."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = [
            KeywordHit(item_id=f"item-{i}", rank=1.0 - i * 0.1, title_snippet=f"Item {i}")
            for i in range(10)
        ]

        monkeypatch.setattr("fourdpocket.ai.factory.get_embedding_provider", lambda: MagicMock())

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        results = service.search(db, "test", user_id=search_user.id, filters=None, offset=3, limit=2)
        assert len(results) == 2
        assert results[0].item_id == "item-3"
        assert results[1].item_id == "item-4"

    def test_search_collection_acl_filters_results(self, db: Session, search_user, search_items, monkeypatch):
        """collection_id filter restricts results to collection items only."""
        from fourdpocket.models.collection import Collection, CollectionItem

        collection = Collection(user_id=search_user.id, name="My Collection")
        db.add(collection)
        db.commit()
        db.refresh(collection)

        col_item = CollectionItem(collection_id=collection.id, item_id=search_items[0].id)
        db.add(col_item)
        db.commit()

        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = [
            KeywordHit(item_id=str(search_items[0].id), rank=1.0, title_snippet="Item 0"),
            KeywordHit(item_id=str(search_items[1].id), rank=0.9, title_snippet="Item 1"),
            KeywordHit(item_id=str(search_items[2].id), rank=0.8, title_snippet="Item 2"),
        ]

        monkeypatch.setattr("fourdpocket.ai.factory.get_embedding_provider", lambda: MagicMock())

        service = _make_service(keyword=mock_keyword, vector=mock_vector)

        filters = SearchFilters(collection_id=collection.id)
        results = service.search(db, "test", user_id=search_user.id, filters=filters, limit=20)
        # Only item 0 should pass the ACL filter
        assert len(results) == 1
        assert results[0].item_id == str(search_items[0].id)

    def test_search_no_results_returns_empty(self, db: Session, search_user, monkeypatch):
        """Both backends return empty — search returns [] without error."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        mock_keyword.search.return_value = []

        monkeypatch.setattr("fourdpocket.ai.factory.get_embedding_provider", lambda: MagicMock())

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        results = service.search(db, "nothing matches", user_id=search_user.id, filters=None, limit=20)
        assert results == []

    def test_rrf_fusion_only_keyword(self, db: Session):
        """RRF fusion with only keyword hits still ranks by keyword position."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()

        service = SearchService(keyword=mock_keyword, vector=mock_vector)
        kw_hits = [
            KeywordHit(item_id="a", rank=1.0, title_snippet="A"),
            KeywordHit(item_id="b", rank=1.0, title_snippet="B"),
            KeywordHit(item_id="c", rank=1.0, title_snippet="C"),
        ]
        results = service._rrf_fusion(kw_hits, [])
        ids = [r.item_id for r in results]
        assert ids == ["a", "b", "c"]

    def test_rrf_fusion_both_backends_overlap(self, db: Session):
        """RRF fusion boosts items appearing in both keyword and vector results."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()

        service = SearchService(keyword=mock_keyword, vector=mock_vector)
        kw_hits = [
            KeywordHit(item_id="a", rank=1.0, title_snippet="A"),
            KeywordHit(item_id="b", rank=1.0, title_snippet="B"),
        ]
        vec_hits = [
            VectorHit(item_id="b", similarity=0.9),
            VectorHit(item_id="c", similarity=0.9),
        ]
        results = service._rrf_fusion(kw_hits, vec_hits)
        ids = [r.item_id for r in results]
        # b is in both, should be first
        assert ids[0] == "b"
        assert set(ids) == {"a", "b", "c"}

    def test_rrf_fusion_empty_keyword(self, db: Session):
        """RRF fusion with only vector hits ranks by vector position."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()

        service = SearchService(keyword=mock_keyword, vector=mock_vector)
        results = service._rrf_fusion([], [VectorHit(item_id="x", similarity=0.9)])
        assert len(results) == 1
        assert results[0].item_id == "x"

    def test_search_reranker_reorders_results(self, db: Session, search_user, monkeypatch):
        """Reranker can change the ordering of merged results."""
        mock_vector = MagicMock()
        mock_vector.search.return_value = []
        mock_keyword = MagicMock()
        id_a = str(uuid.uuid4())
        id_b = str(uuid.uuid4())
        id_c = str(uuid.uuid4())
        mock_keyword.search.return_value = [
            KeywordHit(item_id=id_a, rank=1.0, title_snippet="Doc A"),
            KeywordHit(item_id=id_b, rank=1.0, title_snippet="Doc B"),
            KeywordHit(item_id=id_c, rank=1.0, title_snippet="Doc C"),
        ]

        # Reranker reorders: index 2 first, then 0, then 1
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [(2, 0.95), (0, 0.85), (1, 0.75)]

        mock_settings = MagicMock()
        mock_settings.rerank.enabled = True
        mock_settings.rerank.top_k = 20
        mock_settings.rerank.candidate_pool = 50

        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        service = _make_service(keyword=mock_keyword, vector=mock_vector, reranker=mock_reranker)
        results = service.search(db, "test", user_id=search_user.id, filters=None, limit=20)
        # Reranker changed the order
        assert results[0].item_id == id_c
        assert results[1].item_id == id_a
        assert results[2].item_id == id_b

    def test_delete_item_calls_both_backends(self, db: Session, search_user, monkeypatch):
        """delete_item delegates to both keyword and vector backends."""
        mock_vector = MagicMock()
        mock_keyword = MagicMock()

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        item_id = uuid.uuid4()
        service.delete_item(db, item_id, search_user.id)
        mock_keyword.delete_item.assert_called_once()
        mock_vector.delete_item.assert_called_once()

    def test_index_item_wraps_keyword_backend(self, db: Session, search_user, monkeypatch):
        """index_item delegates to keyword backend, swallows exceptions."""
        mock_vector = MagicMock()
        mock_keyword = MagicMock()

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        service.index_item(db, MagicMock())
        mock_keyword.index_item.assert_called_once()

    def test_index_chunks_wraps_keyword_backend(self, db: Session, search_user, monkeypatch):
        """index_chunks delegates to keyword backend, swallows exceptions."""
        mock_vector = MagicMock()
        mock_keyword = MagicMock()

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        service.index_chunks(db, uuid.uuid4(), search_user.id, [])
        mock_keyword.index_chunks.assert_called_once()

    def test_upsert_item_embedding_calls_vector_backend(self, db: Session, search_user, monkeypatch):
        """upsert_item_embedding delegates to vector backend upsert_item."""
        mock_vector = MagicMock()
        mock_keyword = MagicMock()

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        item_id = uuid.uuid4()
        embedding = [0.1] * 384
        metadata = {"title": "Test Item"}

        service.upsert_item_embedding(item_id, search_user.id, embedding, metadata)

        mock_vector.upsert_item.assert_called_once_with(item_id, search_user.id, embedding, metadata)

    def test_upsert_item_embedding_swallows_exception(self, db: Session, search_user, monkeypatch):
        """upsert_item_embedding logs but does not raise on vector backend failure."""
        mock_vector = MagicMock()
        mock_vector.upsert_item.side_effect = RuntimeError("Vector backend unavailable")
        mock_keyword = MagicMock()

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        item_id = uuid.uuid4()

        # Should not raise
        service.upsert_item_embedding(item_id, search_user.id, [0.1] * 384)

    def test_upsert_chunk_embedding_calls_vector_backend(self, db: Session, search_user, monkeypatch):
        """upsert_chunk_embedding delegates to vector backend upsert_chunk."""
        mock_vector = MagicMock()
        mock_keyword = MagicMock()

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        chunk_id = uuid.uuid4()
        item_id = uuid.uuid4()
        embedding = [0.2] * 384
        metadata = {"heading": "Introduction"}

        service.upsert_chunk_embedding(chunk_id, item_id, search_user.id, embedding, metadata)

        mock_vector.upsert_chunk.assert_called_once_with(chunk_id, item_id, search_user.id, embedding, metadata)

    def test_upsert_chunk_embedding_swallows_exception(self, db: Session, search_user, monkeypatch):
        """upsert_chunk_embedding logs but does not raise on vector backend failure."""
        mock_vector = MagicMock()
        mock_vector.upsert_chunk.side_effect = RuntimeError("Vector backend unavailable")
        mock_keyword = MagicMock()

        service = _make_service(keyword=mock_keyword, vector=mock_vector)
        chunk_id = uuid.uuid4()
        item_id = uuid.uuid4()

        # Should not raise
        service.upsert_chunk_embedding(chunk_id, item_id, search_user.id, [0.2] * 384)
