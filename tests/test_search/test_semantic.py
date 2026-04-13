"""Tests for semantic search module — ChromaDB-backed vector operations with mocked client."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from fourdpocket.search import semantic


class TestSemanticAddEmbedding:
    """Tests for add_embedding() — stores embedding in ChromaDB."""

    @pytest.fixture
    def user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def item_id(self):
        return uuid.uuid4()

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_add_embedding_sets_user_id_in_metadata(self, mock_get_collection, mock_get_client, user_id, item_id):
        """user_id is injected into metadata before upsert."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        semantic.add_embedding(
            item_id=item_id,
            user_id=user_id,
            embedding=[0.1] * 384,
            metadata={"title": "Test"},
        )

        call_kwargs = mock_collection.upsert.call_args
        meta = call_kwargs.kwargs["metadatas"][0]
        assert meta["user_id"] == str(user_id)
        assert meta["title"] == "Test"


class TestSemanticQuerySimilar:
    """Tests for query_similar() — finds similar items by embedding."""

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_query_similar_excludes_self(self, mock_get_collection, mock_get_client):
        """The query item itself is excluded from results."""
        user_id = uuid.uuid4()
        item_id = uuid.uuid4()

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {
            "embeddings": [[0.1] * 384],
        }
        mock_collection.query.return_value = {
            "ids": [[str(item_id), "other-item"]],
            "distances": [[0.0, 0.3]],
        }

        results = semantic.query_similar(item_id, user_id, limit=5)

        ids = [r["item_id"] for r in results]
        assert str(item_id) not in ids
        assert "other-item" in ids

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_query_similar_no_embedding_returns_empty(self, mock_get_collection, mock_get_client):
        """Item with no embedding returns empty list."""
        user_id = uuid.uuid4()
        item_id = uuid.uuid4()

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {"embeddings": []}

        results = semantic.query_similar(item_id, user_id)
        assert results == []

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_query_similar_converts_distance_to_similarity(self, mock_get_collection, mock_get_client):
        """Distance is converted to similarity (1 - distance for cosine)."""
        user_id = uuid.uuid4()
        item_id = uuid.uuid4()

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {
            "embeddings": [[0.1] * 384],
        }
        mock_collection.query.return_value = {
            "ids": [["other-item"]],
            "distances": [[0.2]],
        }

        results = semantic.query_similar(item_id, user_id, limit=5)
        assert results[0]["similarity"] == 0.8


class TestSemanticSearchByText:
    """Tests for search_by_text() — embed query and search ChromaDB."""

    @patch("fourdpocket.ai.factory.get_embedding_provider")
    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_search_by_text_embeds_query(self, mock_get_collection, mock_get_client, mock_get_provider):
        """search_by_text calls embed_single on the provider."""
        user_id = uuid.uuid4()

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.5] * 384
        mock_get_provider.return_value = mock_provider

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.query.return_value = {
            "ids": [["item1"]],
            "distances": [[0.0]],
        }

        results = semantic.search_by_text("test query", user_id)

        mock_provider.embed_single.assert_called_once_with("test query")
        assert len(results) == 1

    @patch("fourdpocket.ai.factory.get_embedding_provider")
    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_search_by_text_returns_empty_on_no_embedding(self, mock_get_collection, mock_get_client, mock_get_provider):
        """No embedding from provider returns empty list."""
        user_id = uuid.uuid4()

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = None
        mock_get_provider.return_value = mock_provider

        results = semantic.search_by_text("test query", user_id)
        assert results == []


class TestSemanticAddChunkEmbedding:
    """Tests for add_chunk_embedding() — stores chunk embedding with item_id in metadata."""

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_add_chunk_embedding_sets_is_chunk_flag(self, mock_get_collection, mock_get_client):
        """is_chunk metadata flag is set for chunk documents."""
        chunk_id = uuid.uuid4()
        item_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        semantic.add_chunk_embedding(
            chunk_id=chunk_id,
            user_id=user_id,
            item_id=item_id,
            embedding=[0.1] * 384,
            metadata={},
        )

        call_kwargs = mock_collection.upsert.call_args
        meta = call_kwargs.kwargs["metadatas"][0]
        assert meta["is_chunk"] == "true"
        assert meta["item_id"] == str(item_id)


class TestSemanticDeleteChunkEmbeddings:
    """Tests for delete_chunk_embeddings() — removes all chunk embeddings for an item."""

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_delete_chunk_embeddings(self, mock_get_collection, mock_get_client):
        """delete_chunk_embeddings finds and deletes all matching chunks."""
        item_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.return_value = {
            "ids": ["chunk-1", "chunk-2", "chunk-3"],
        }

        semantic.delete_chunk_embeddings(user_id, item_id)

        mock_collection.get.assert_called_once()
        mock_collection.delete.assert_called_once_with(ids=["chunk-1", "chunk-2", "chunk-3"])


class TestSemanticSearchChunksByText:
    """Tests for search_chunks_by_text() — chunk-level semantic search."""

    @patch("fourdpocket.ai.factory.get_embedding_provider")
    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_search_chunks_by_text(self, mock_get_collection, mock_get_client, mock_get_provider):
        """Returns {chunk_id, item_id, similarity} dicts."""
        user_id = uuid.uuid4()

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.5] * 384
        mock_get_provider.return_value = mock_provider

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.query.return_value = {
            "ids": [["chunk1", "chunk2"]],
            "distances": [[0.1, 0.3]],
            "metadatas": [
                [
                    {"item_id": "item1", "is_chunk": "true"},
                    {"item_id": "item2", "is_chunk": "true"},
                ]
            ],
        }

        results = semantic.search_chunks_by_text("test query", user_id, limit=10)

        assert len(results) == 2
        assert results[0]["chunk_id"] == "chunk1"
        assert results[0]["item_id"] == "item1"
        assert results[0]["similarity"] == 0.9


class TestSemanticErrorHandling:
    """Tests that semantic functions handle errors gracefully."""

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_query_similar_handles_exception(self, mock_get_collection, mock_get_client):
        """Exception in ChromaDB query returns empty list."""
        user_id = uuid.uuid4()
        item_id = uuid.uuid4()

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.get.side_effect = Exception("ChromaDB error")

        results = semantic.query_similar(item_id, user_id)
        assert results == []

    @patch("fourdpocket.ai.factory.get_embedding_provider")
    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_search_by_text_handles_exception(self, mock_get_collection, mock_get_client, mock_get_provider):
        """Exception in ChromaDB query returns empty list."""
        user_id = uuid.uuid4()

        mock_provider = MagicMock()
        mock_provider.embed_single.return_value = [0.5] * 384
        mock_get_provider.return_value = mock_provider

        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.query.side_effect = Exception("ChromaDB error")

        results = semantic.search_by_text("test", user_id)
        assert results == []
