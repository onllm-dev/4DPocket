"""Tests for ai/nvidia_embeddings.py — NVIDIA embedding provider with local fallback."""

from unittest.mock import MagicMock, patch


class TestNvidiaEmbeddingProvider:
    """Tests for NvidiaEmbeddingProvider."""

    def test_embed_uses_nvidia_when_api_key_set(self, monkeypatch):
        """When embedding_provider=nvidia and nvidia_api_key is set, uses NVIDIA API."""
        class FakeAI:
            nvidia_api_key = "nvda-test-key"
            embedding_provider = "nvidia"

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.nvidia_embeddings.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.nvidia_embeddings import NvidiaEmbeddingProvider
            provider = NvidiaEmbeddingProvider()
            result = provider.embed(["test text"])

            mock_client.embeddings.create.assert_called_once()
            call_kwargs = mock_client.embeddings.create.call_args.kwargs
            assert call_kwargs["model"] == "nvidia/nv-embed-v1"
            assert call_kwargs["input"] == ["test text"]
            assert call_kwargs["encoding_format"] == "float"
            assert result == [[0.1, 0.2, 0.3]]

    def test_embed_falls_back_to_local_on_error(self, monkeypatch):
        """NVIDIA API error → falls back to local embeddings."""
        class FakeAI:
            nvidia_api_key = "nvda-test-key"
            embedding_provider = "nvidia"

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.nvidia_embeddings.get_settings", lambda: FakeSettings())

        mock_local_embedder = MagicMock()
        mock_local_embedder.embed.return_value = [[0.4, 0.5, 0.6]]

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create = MagicMock(side_effect=Exception("NVIDIA API error"))
            mock_openai_cls.return_value = mock_client

            # get_local_embedder is imported inside _embed_local from local_embeddings module
            with patch(
                "fourdpocket.ai.local_embeddings.get_local_embedder",
                return_value=mock_local_embedder
            ):
                from fourdpocket.ai.nvidia_embeddings import NvidiaEmbeddingProvider
                provider = NvidiaEmbeddingProvider()
                result = provider.embed(["test text"])

                # Falls back to local
                assert result == [[0.4, 0.5, 0.6]]

    def test_embed_uses_local_when_no_api_key(self, monkeypatch):
        """When nvidia_api_key is empty, uses local embeddings directly."""
        class FakeAI:
            nvidia_api_key = ""
            embedding_provider = "nvidia"

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.nvidia_embeddings.get_settings", lambda: FakeSettings())

        mock_local_embedder = MagicMock()
        mock_local_embedder.embed.return_value = [[0.7, 0.8, 0.9]]

        with patch(
            "fourdpocket.ai.local_embeddings.get_local_embedder",
            return_value=mock_local_embedder
        ):
            from fourdpocket.ai.nvidia_embeddings import NvidiaEmbeddingProvider
            provider = NvidiaEmbeddingProvider()
            result = provider.embed(["test text"])

            assert result == [[0.7, 0.8, 0.9]]

    def test_embed_single_returns_single_vector(self, monkeypatch):
        """embed_single() calls embed() with single text and returns first result."""
        class FakeAI:
            nvidia_api_key = "nvda-test-key"
            embedding_provider = "nvidia"

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.nvidia_embeddings.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.nvidia_embeddings import NvidiaEmbeddingProvider
            provider = NvidiaEmbeddingProvider()
            result = provider.embed_single("single text")

            assert result == [0.1, 0.2, 0.3]

    def test_embed_empty_list_returns_empty(self, monkeypatch):
        """embed() with empty list returns empty list."""
        class FakeAI:
            nvidia_api_key = "nvda-test-key"
            embedding_provider = "nvidia"

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.nvidia_embeddings.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.data = []

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.embeddings.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.nvidia_embeddings import NvidiaEmbeddingProvider
            provider = NvidiaEmbeddingProvider()
            result = provider.embed([])

            assert result == []
