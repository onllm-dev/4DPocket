"""Tests for the legacy ai_enrichment.enrich_item task."""

import uuid

import pytest
from sqlmodel import Session, select

from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.item_chunk import ItemChunk


@pytest.fixture
def enrich_user(db: Session):
    from fourdpocket.models.user import User

    user = User(
        email="enrichtest@example.com",
        username="enrichuser",
        password_hash="$2b$12$fakehash",
        display_name="Enrich Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def enrich_item_with_content(db: Session, enrich_user):
    item = KnowledgeItem(
        user_id=enrich_user.id,
        title="Test Article",
        content=(
            "Machine learning is transforming software engineering. "
            "Large language models can generate code, debug issues, and write tests."
        ),
        url="https://example.com/article",
        item_type="url",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@pytest.fixture
def enrich_item_no_content(db: Session, enrich_user):
    item = KnowledgeItem(
        user_id=enrich_user.id,
        title="No Content Item",
        content=None,
        url="https://example.com/empty",
        item_type="url",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


class TestEnrichItemNotFound:
    def test_enrich_item_not_found(self, db: Session, monkeypatch):
        """Item not found returns error dict."""
        from fourdpocket.workers.ai_enrichment import enrich_item

        # Patch get_engine at its definition source
        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        # Use call_local() for synchronous Huey task execution
        result = enrich_item.call_local(str(uuid.uuid4()), str(uuid.uuid4()))
        assert result["status"] == "error"
        assert "not found" in result["error"]


class TestEnrichItemSuccess:
    def test_enrich_item_full_success(
        self, db: Session, enrich_item_with_content, enrich_user, monkeypatch
    ):
        """Full pipeline succeeds when all steps work."""
        from unittest.mock import MagicMock

        from fourdpocket.workers.ai_enrichment import enrich_item

        # Patch get_engine at its definition source
        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        # Mock AI functions at their source modules
        mock_tags = [{"name": "ai", "confidence": 0.9}]
        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item", lambda **kw: mock_tags
        )
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item", lambda *a, **kw: "Test summary"
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy", lambda *a, **kw: None
        )

        # Mock embedding provider
        class FakeEmbedder:
            dimensions = 384

            def embed_single(self, text):
                return [0.1] * 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        fake_provider = FakeEmbedder()
        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: fake_provider
        )

        # Mock add_embedding and add_chunk_embedding (no-op)
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding", lambda **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding", lambda **kw: None
        )

        # Mock get_settings for chunking
        mock_settings = MagicMock()
        mock_settings.search.chunk_size_tokens = 256
        mock_settings.search.chunk_overlap_tokens = 40
        mock_settings.search.max_chunks_per_item = 20
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        # Mock search service index_item
        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=lambda db, item: None),
        )

        result = enrich_item.call_local(str(enrich_item_with_content.id), str(enrich_user.id))

        assert result["status"] == "success"
        assert result["item_id"] == str(enrich_item_with_content.id)
        assert "chunking" in result["steps"]
        assert "tagging" in result["steps"]
        assert "hierarchy" in result["steps"]
        assert "summarization" in result["steps"]
        assert "embedding" in result["steps"]
        assert "chunk_embedding" in result["steps"]
        assert "indexing" in result["steps"]

        # Verify chunks were created
        chunks = db.exec(
            select(ItemChunk).where(ItemChunk.item_id == enrich_item_with_content.id)
        ).all()
        assert len(chunks) >= 1

    def test_enrich_item_no_content_skips_chunking(
        self, db: Session, enrich_item_no_content, enrich_user, monkeypatch
    ):
        """Item with no content skips chunking step."""
        from unittest.mock import MagicMock

        from fourdpocket.workers.ai_enrichment import enrich_item

        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item", lambda **kw: []
        )
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item", lambda *a, **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy", lambda *a, **kw: None
        )

        class FakeEmbedder:
            dimensions = 384

            def embed_single(self, text):
                return [0.1] * 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        fake_provider = FakeEmbedder()
        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: fake_provider
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding", lambda **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding", lambda **kw: None
        )

        mock_settings = MagicMock()
        mock_settings.search.chunk_size_tokens = 256
        mock_settings.search.chunk_overlap_tokens = 40
        mock_settings.search.max_chunks_per_item = 20
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=lambda db, item: None),
        )

        result = enrich_item.call_local(str(enrich_item_no_content.id), str(enrich_user.id))

        assert result["status"] == "success"
        assert result["steps"]["chunking"]["status"] == "skipped"
        assert result["steps"]["chunking"]["reason"] == "no content"


class TestEnrichItemChunkingFailure:
    def test_chunking_failure_continues_pipeline(
        self, db: Session, enrich_item_with_content, enrich_user, monkeypatch
    ):
        """Chunking failure does not stop the rest of the pipeline."""
        from unittest.mock import MagicMock

        from fourdpocket.workers.ai_enrichment import enrich_item

        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        # Make chunk_text raise at its source module
        def chunk_error(*a, **kw):
            raise Exception("chunk error")

        monkeypatch.setattr("fourdpocket.search.chunking.chunk_text", chunk_error)

        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item", lambda **kw: [{"name": "test", "confidence": 0.8}]
        )
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item", lambda *a, **kw: "summary"
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy", lambda *a, **kw: None
        )

        class FakeEmbedder:
            dimensions = 384

            def embed_single(self, text):
                return [0.1] * 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        fake_provider = FakeEmbedder()
        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: fake_provider
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding", lambda **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding", lambda **kw: None
        )

        mock_settings = MagicMock()
        mock_settings.search.chunk_size_tokens = 256
        mock_settings.search.chunk_overlap_tokens = 40
        mock_settings.search.max_chunks_per_item = 20
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=lambda db, item: None),
        )

        result = enrich_item.call_local(str(enrich_item_with_content.id), str(enrich_user.id))

        assert result["status"] == "success"
        assert result["steps"]["chunking"]["status"] == "error"
        assert "chunk error" in result["steps"]["chunking"]["error"]
        # Other steps should still run
        assert result["steps"]["tagging"]["status"] == "success"


class TestEnrichItemTaggingFailure:
    def test_tagging_failure_continues_pipeline(
        self, db: Session, enrich_item_with_content, enrich_user, monkeypatch
    ):
        """Tagging failure does not stop summarization, embedding, or indexing."""
        from unittest.mock import MagicMock

        from fourdpocket.workers.ai_enrichment import enrich_item

        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item",
            lambda **kw: (_ for _ in ()).throw(Exception("tag error")),
        )
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item", lambda *a, **kw: "summary"
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy", lambda *a, **kw: None
        )

        class FakeEmbedder:
            dimensions = 384

            def embed_single(self, text):
                return [0.1] * 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        fake_provider = FakeEmbedder()
        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: fake_provider
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding", lambda **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding", lambda **kw: None
        )

        mock_settings = MagicMock()
        mock_settings.search.chunk_size_tokens = 256
        mock_settings.search.chunk_overlap_tokens = 40
        mock_settings.search.max_chunks_per_item = 20
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=lambda db, item: None),
        )

        result = enrich_item.call_local(str(enrich_item_with_content.id), str(enrich_user.id))

        assert result["status"] == "success"
        assert result["steps"]["tagging"]["status"] == "error"
        # Note: hierarchy fails because tags is unbound when tagging threw
        assert result["steps"]["hierarchy"]["status"] == "error"
        assert result["steps"]["summarization"]["status"] == "success"
        assert result["steps"]["embedding"]["status"] == "success"


class TestEnrichItemSummarizationFailure:
    def test_summarization_failure_continues(
        self, db: Session, enrich_item_with_content, enrich_user, monkeypatch
    ):
        """Summarization failure does not stop embedding or indexing."""
        from unittest.mock import MagicMock

        from fourdpocket.workers.ai_enrichment import enrich_item

        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item", lambda **kw: [{"name": "test", "confidence": 0.9}]
        )
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item",
            lambda *a, **kw: (_ for _ in ()).throw(Exception("summarize error")),
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy", lambda *a, **kw: None
        )

        class FakeEmbedder:
            dimensions = 384

            def embed_single(self, text):
                return [0.1] * 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        fake_provider = FakeEmbedder()
        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: fake_provider
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding", lambda **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding", lambda **kw: None
        )

        mock_settings = MagicMock()
        mock_settings.search.chunk_size_tokens = 256
        mock_settings.search.chunk_overlap_tokens = 40
        mock_settings.search.max_chunks_per_item = 20
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=lambda db, item: None),
        )

        result = enrich_item.call_local(str(enrich_item_with_content.id), str(enrich_user.id))

        assert result["status"] == "success"
        assert result["steps"]["summarization"]["status"] == "error"
        assert result["steps"]["embedding"]["status"] == "success"
        assert result["steps"]["indexing"]["status"] == "success"


class TestEnrichItemEmbeddingFailure:
    def test_embedding_failure_continues_to_chunk_embedding(
        self, db: Session, enrich_item_with_content, enrich_user, monkeypatch
    ):
        """Item-level embedding failure does not stop chunk embedding or indexing."""
        from unittest.mock import MagicMock

        from fourdpocket.workers.ai_enrichment import enrich_item

        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item", lambda **kw: [{"name": "test", "confidence": 0.9}]
        )
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item", lambda *a, **kw: "summary"
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy", lambda *a, **kw: None
        )

        # Make embed_single raise but embed work
        class FakeEmbedder:
            dimensions = 384

            def embed_single(self, text):
                raise Exception("embedding error")

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        fake_provider = FakeEmbedder()
        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: fake_provider
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding", lambda **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding", lambda **kw: None
        )

        mock_settings = MagicMock()
        mock_settings.search.chunk_size_tokens = 256
        mock_settings.search.chunk_overlap_tokens = 40
        mock_settings.search.max_chunks_per_item = 20
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=lambda db, item: None),
        )

        result = enrich_item.call_local(str(enrich_item_with_content.id), str(enrich_user.id))

        assert result["status"] == "success"
        assert result["steps"]["embedding"]["status"] == "error"
        assert result["steps"]["chunk_embedding"]["status"] == "success"
        assert result["steps"]["indexing"]["status"] == "success"


class TestEnrichItemIndexingFailure:
    def test_indexing_failure_still_returns_success(
        self, db: Session, enrich_item_with_content, enrich_user, monkeypatch
    ):
        """Indexing failure is caught and logged but pipeline returns success."""
        from unittest.mock import MagicMock

        from fourdpocket.workers.ai_enrichment import enrich_item

        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item", lambda **kw: [{"name": "test", "confidence": 0.9}]
        )
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item", lambda *a, **kw: "summary"
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy", lambda *a, **kw: None
        )

        class FakeEmbedder:
            dimensions = 384

            def embed_single(self, text):
                return [0.1] * 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        fake_provider = FakeEmbedder()
        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: fake_provider
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding", lambda **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding", lambda **kw: None
        )

        mock_settings = MagicMock()
        mock_settings.search.chunk_size_tokens = 256
        mock_settings.search.chunk_overlap_tokens = 40
        mock_settings.search.max_chunks_per_item = 20
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        # Make index_item raise
        def index_error(db, item):
            raise Exception("index error")

        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=index_error),
        )

        result = enrich_item.call_local(str(enrich_item_with_content.id), str(enrich_user.id))

        assert result["status"] == "success"
        assert result["steps"]["indexing"]["status"] == "error"
        assert "index error" in result["steps"]["indexing"]["error"]


class TestEnrichItemEmptyEmbedding:
    def test_empty_embedding_skipped(
        self, db: Session, enrich_item_with_content, enrich_user, monkeypatch
    ):
        """None embedding from provider is recorded as skipped."""
        from unittest.mock import MagicMock

        from fourdpocket.workers.ai_enrichment import enrich_item

        monkeypatch.setattr("fourdpocket.db.session.get_engine", lambda: db.get_bind())

        monkeypatch.setattr(
            "fourdpocket.ai.tagger.auto_tag_item", lambda **kw: [{"name": "test", "confidence": 0.9}]
        )
        monkeypatch.setattr(
            "fourdpocket.ai.summarizer.summarize_item", lambda *a, **kw: "summary"
        )
        monkeypatch.setattr(
            "fourdpocket.ai.hierarchy.apply_hierarchy", lambda *a, **kw: None
        )

        # Return None embedding
        class FakeEmbedder:
            dimensions = 384

            def embed_single(self, text):
                return None

            def embed(self, texts):
                return [None] * len(texts)

        fake_provider = FakeEmbedder()
        monkeypatch.setattr(
            "fourdpocket.ai.factory.get_embedding_provider", lambda: fake_provider
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_embedding", lambda **kw: None
        )
        monkeypatch.setattr(
            "fourdpocket.search.semantic.add_chunk_embedding", lambda **kw: None
        )

        mock_settings = MagicMock()
        mock_settings.search.chunk_size_tokens = 256
        mock_settings.search.chunk_overlap_tokens = 40
        mock_settings.search.max_chunks_per_item = 20
        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        monkeypatch.setattr(
            "fourdpocket.search.get_search_service",
            lambda: MagicMock(index_item=lambda db, item: None),
        )

        result = enrich_item.call_local(str(enrich_item_with_content.id), str(enrich_user.id))

        assert result["status"] == "success"
        assert result["steps"]["embedding"]["status"] == "skipped"
        assert result["steps"]["embedding"]["reason"] == "empty embedding"
