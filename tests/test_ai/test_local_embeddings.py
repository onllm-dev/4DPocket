"""Tests for ai/local_embeddings.py — Local sentence-transformers embedding provider."""

from unittest.mock import MagicMock, patch


class TestLocalEmbeddingProvider:
    """Tests for LocalEmbeddingProvider.embed() and embed_single()."""

    def test_embed_calls_model_encode(self, monkeypatch):
        """embed() calls sentence_transformers model.encode() with correct args."""
        mock_model = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.tolist.return_value = [[0.1, 0.2, 0.3]]
        mock_model.encode.return_value = mock_embeddings

        with patch(
            "fourdpocket.ai.local_embeddings._load_model",
            return_value=mock_model
        ):
            from fourdpocket.ai.local_embeddings import LocalEmbeddingProvider
            provider = LocalEmbeddingProvider()
            result = provider.embed(["hello world"])

            mock_model.encode.assert_called_once()
            call_args = mock_model.encode.call_args
            assert call_args.kwargs["show_progress_bar"] is False
            assert call_args.kwargs["normalize_embeddings"] is True
            assert result == [[0.1, 0.2, 0.3]]

    def test_embed_single_calls_embed(self, monkeypatch):
        """embed_single() calls embed() with a single-text list and returns first."""
        mock_model = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.tolist.return_value = [[0.5, 0.6, 0.7]]
        mock_model.encode.return_value = mock_embeddings

        with patch(
            "fourdpocket.ai.local_embeddings._load_model",
            return_value=mock_model
        ):
            from fourdpocket.ai.local_embeddings import LocalEmbeddingProvider
            provider = LocalEmbeddingProvider()
            result = provider.embed_single("single text")

            assert result == [0.5, 0.6, 0.7]

    def test_embed_empty_list(self, monkeypatch):
        """embed() with empty list returns empty list."""
        mock_model = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.tolist.return_value = []
        mock_model.encode.return_value = mock_embeddings

        with patch(
            "fourdpocket.ai.local_embeddings._load_model",
            return_value=mock_model
        ):
            from fourdpocket.ai.local_embeddings import LocalEmbeddingProvider
            provider = LocalEmbeddingProvider()
            result = provider.embed([])

            assert result == []


class TestGetLocalEmbedder:
    """Tests for get_local_embedder() singleton."""

    def test_returns_singleton_instance(self, monkeypatch):
        """get_local_embedder() returns the same instance on repeated calls."""
        # Reset module-level state before test
        import fourdpocket.ai.local_embeddings as le_module
        le_module._instance = None
        le_module._model = None

        mock_model = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.tolist.return_value = [[0.1]]
        mock_model.encode.return_value = mock_embeddings

        with patch(
            "fourdpocket.ai.local_embeddings._load_model",
            return_value=mock_model
        ):
            from fourdpocket.ai.local_embeddings import LocalEmbeddingProvider, get_local_embedder

            provider1 = get_local_embedder()
            provider2 = get_local_embedder()

            assert provider1 is provider2
            assert isinstance(provider1, LocalEmbeddingProvider)
