"""Tests for LocalReranker — mocked sentence_transformers."""

from unittest.mock import MagicMock, patch

from fourdpocket.search.reranker import LocalReranker, NullReranker, build_reranker


class TestNullReranker:
    """NullReranker is tested here alongside LocalReranker for completeness."""

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


# === PHASE 1A MOPUP ADDITIONS ===

class TestLocalReranker:
    """Tests for LocalReranker with mocked sentence_transformers."""

    def test_local_reranker_init(self):
        """Reranker initializes with model name, no model loaded yet."""
        reranker = LocalReranker()
        assert reranker._model is None
        assert reranker._load_failed is False
        assert reranker._model_name == "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def test_local_reranker_init_custom_model_name(self):
        """Custom model name is stored."""
        reranker = LocalReranker(model_name="cross-encoder/ms-marco-MiniLM-L-12-v2")
        assert reranker._model_name == "cross-encoder/ms-marco-MiniLM-L-12-v2"

    def test_local_reranker_load_import_error(self, monkeypatch):
        """ImportError from sentence_transformers sets _load_failed flag."""
        def raise_import_error(*args, **kwargs):
            if args[0] == "sentence_transformers":
                raise ImportError("No module named 'sentence_transformers'")
            return __import__(*args, **kwargs)

        monkeypatch.setattr("builtins.__import__", raise_import_error)
        reranker = LocalReranker()
        reranker._load()
        assert reranker._load_failed is True
        assert reranker._model is None

    def test_local_reranker_load_generic_error(self):
        """Generic exception during load sets _load_failed flag."""
        with patch("sentence_transformers.CrossEncoder", side_effect=RuntimeError("Model file corrupted")):
            reranker = LocalReranker()
            reranker._load()
            assert reranker._load_failed is True

    def test_local_reranker_rerank_happy(self):
        """rerank returns sorted (idx, score) tuples on success."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.9, 0.8, 0.7]

        reranker = LocalReranker()
        reranker._model = mock_model

        result = reranker.rerank("query", ["doc1", "doc2", "doc3"], top_k=2)
        assert result is not None
        assert len(result) == 2
        # Highest score first
        assert result[0][0] == 0  # index of doc1 (score 0.9)
        assert result[0][1] == 0.9
        assert result[1][0] == 1  # index of doc2 (score 0.8)

    def test_local_reranker_rerank_model_not_loaded(self):
        """rerank returns [] when model failed to load, signaling caller to skip reranking."""
        reranker = LocalReranker()
        reranker._model = None
        reranker._load_failed = True

        result = reranker.rerank("query", ["doc1"], top_k=1)
        assert result == []

    def test_local_reranker_rerank_empty_docs(self):
        """rerank with empty docs list returns empty list."""
        reranker = LocalReranker()
        reranker._model = MagicMock()

        result = reranker.rerank("query", [], top_k=5)
        assert result == []

    def test_local_reranker_rerank_top_k_limits_results(self):
        """rerank returns at most top_k results."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.1, 0.9, 0.5, 0.3, 0.8]

        reranker = LocalReranker()
        reranker._model = mock_model

        result = reranker.rerank("query", ["a", "b", "c", "d", "e"], top_k=3)
        assert len(result) == 3

    def test_local_reranker_load_idempotent(self):
        """_load is idempotent — calling twice doesn't reload."""
        mock_model_instance = MagicMock()
        mock_cls = MagicMock(return_value=mock_model_instance)

        with patch("sentence_transformers.CrossEncoder", mock_cls):
            reranker = LocalReranker()
            reranker._load()
            reranker._load()
            reranker._load()

        # CrossEncoder called exactly once
        assert mock_cls.call_count == 1

    def test_local_reranker_score_types(self):
        """rerank returns (int, float) tuples."""
        mock_model = MagicMock()
        mock_model.predict.return_value = [0.123456]

        reranker = LocalReranker()
        reranker._model = mock_model

        result = reranker.rerank("query", ["doc1"], top_k=1)
        assert isinstance(result[0][0], int)
        assert isinstance(result[0][1], float)


class TestBuildReranker:
    """Tests for build_reranker factory."""

    def test_build_reranker_disabled(self, monkeypatch):
        """enabled=False returns NullReranker."""
        mock_settings = MagicMock()
        mock_settings.rerank = MagicMock()
        mock_settings.rerank.enabled = False

        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)
        result = build_reranker(mock_settings)
        assert isinstance(result, NullReranker)

    def test_build_reranker_no_rerank_config(self, monkeypatch):
        """No rerank key in settings returns NullReranker."""
        mock_settings = MagicMock(spec=[])  # has no rerank attribute

        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)
        result = build_reranker(mock_settings)
        assert isinstance(result, NullReranker)

    def test_build_reranker_enabled(self, monkeypatch):
        """enabled=True returns LocalReranker with configured model."""
        mock_settings = MagicMock()
        mock_settings.rerank.enabled = True
        mock_settings.rerank.model = "cross-encoder/ms-marco-MiniLM-L-12-v2"

        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        with patch("fourdpocket.search.reranker.LocalReranker") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            result = build_reranker(mock_settings)

        mock_cls.assert_called_once_with(model_name="cross-encoder/ms-marco-MiniLM-L-12-v2")
        assert result is mock_instance

    def test_build_reranker_uses_default_model(self, monkeypatch):
        """No model specified — uses default model name."""
        mock_settings = MagicMock()
        mock_settings.rerank.enabled = True
        del mock_settings.rerank.model  # attribute missing

        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)

        with patch("fourdpocket.search.reranker.LocalReranker") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            build_reranker(mock_settings)

        # Default model name passed
        mock_cls.assert_called_once_with(
            model_name="cross-encoder/ms-marco-MiniLM-L-6-v2"
        )

    def test_build_reranker_accepts_none_settings(self, monkeypatch):
        """None settings is handled gracefully — delegates to get_settings."""
        mock_settings = MagicMock()
        mock_settings.rerank = None

        monkeypatch.setattr("fourdpocket.config.get_settings", lambda: mock_settings)
        result = build_reranker(None)
        assert isinstance(result, NullReranker)
