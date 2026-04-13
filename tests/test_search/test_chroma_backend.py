"""Tests for ChromaBackend — ChromaDB vector backend with mocked client."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from fourdpocket.search.backends.chroma_backend import ChromaBackend


class TestChromaBackend:
    """Test ChromaBackend with mocked ChromaDB client."""

    @pytest.fixture
    def user_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def item_id(self):
        return uuid.uuid4()

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_upsert_item(self, mock_get_collection, mock_get_client, user_id, item_id):
        """upsert_item calls add_embedding with correct args."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        backend = ChromaBackend()
        backend.upsert_item(
            item_id=item_id,
            user_id=user_id,
            embedding=[0.1] * 384,
            metadata={"title": "Test Item"},
        )

        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args
        assert call_kwargs.kwargs["ids"] == [str(item_id)]
        assert call_kwargs.kwargs["embeddings"] == [[0.1] * 384]

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_upsert_chunk(self, mock_get_collection, mock_get_client, user_id, item_id):
        """upsert_chunk calls add_chunk_embedding with correct args."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        backend = ChromaBackend()
        chunk_id = uuid.uuid4()
        backend.upsert_chunk(
            chunk_id=chunk_id,
            item_id=item_id,
            user_id=user_id,
            embedding=[0.2] * 384,
            metadata={},
        )

        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args
        assert call_kwargs.kwargs["ids"] == [str(chunk_id)]

    @patch("fourdpocket.search.semantic.delete_chunk_embeddings")
    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_delete_item(self, mock_get_collection, mock_get_client, mock_delete_chunks, user_id, item_id):
        """delete_item removes item and chunk embeddings."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        backend = ChromaBackend()
        backend.delete_item(item_id=item_id, user_id=user_id)

        mock_delete_chunks.assert_called_once_with(user_id, item_id)
        mock_collection.delete.assert_called_once_with(ids=[str(item_id)])

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_search_returns_vector_hits(self, mock_get_collection, mock_get_client, user_id):
        """search returns deduplicated VectorHit list."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        # Simulate ChromaDB query result with duplicates
        mock_collection.query.return_value = {
            "ids": [["item1", "item2", "item1"]],
            "distances": [[0.1, 0.2, 0.15]],
            "metadatas": [
                [
                    {"item_id": "item1"},
                    {"item_id": "item2"},
                    {"item_id": "item1"},
                ]
            ],
        }

        backend = ChromaBackend()
        hits = backend.search(
            user_id=user_id,
            embedding=[0.1] * 384,
            k=10,
        )

        assert len(hits) == 2  # item1 deduplicated
        item_ids = {h.item_id for h in hits}
        assert "item1" in item_ids
        assert "item2" in item_ids

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_search_handles_chunk_ids(self, mock_get_collection, mock_get_client, user_id):
        """Chunks with is_chunk=true set chunk_id on VectorHit."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        mock_collection.query.return_value = {
            "ids": [["chunk1", "chunk2"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [
                [
                    {"item_id": "item1", "is_chunk": "true"},
                    {"item_id": "item2", "is_chunk": "true"},
                ]
            ],
        }

        backend = ChromaBackend()
        hits = backend.search(
            user_id=user_id,
            embedding=[0.1] * 384,
            k=10,
        )

        assert len(hits) == 2
        assert hits[0].chunk_id == "chunk1"
        assert hits[1].chunk_id == "chunk2"

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_search_returns_empty_on_exception(self, mock_get_collection, mock_get_client, user_id):
        """Exception during search returns empty list gracefully."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        mock_collection.query.side_effect = Exception("ChromaDB error")

        backend = ChromaBackend()
        hits = backend.search(
            user_id=user_id,
            embedding=[0.1] * 384,
            k=10,
        )

        assert hits == []

    @patch("fourdpocket.search.semantic._get_client")
    @patch("fourdpocket.search.semantic._get_collection")
    def test_search_similarity_calculation(self, mock_get_collection, mock_get_client, user_id):
        """Similarity is correctly computed from cosine distance."""
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection

        # Distance 0.0 → similarity 1.0, distance 1.0 → similarity 0.0
        mock_collection.query.return_value = {
            "ids": [["item1", "item2", "item3"]],
            "distances": [[0.0, 0.5, 1.0]],
            "metadatas": [[{}, {}, {}]],
        }

        backend = ChromaBackend()
        hits = backend.search(
            user_id=user_id,
            embedding=[0.1] * 384,
            k=3,
        )

        assert len(hits) == 3
        # Distances: 0.0→1.0, 0.5→0.5, 1.0→0.0
        assert hits[0].similarity == 1.0
        assert hits[1].similarity == 0.5
        assert hits[2].similarity == 0.0
