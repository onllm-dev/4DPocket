"""Tests for ai/factory.py."""

from unittest.mock import MagicMock

from fourdpocket.ai import factory


class TestGetResolvedAIConfig:
    """Tests for get_resolved_ai_config()."""

    def test_returns_dict_with_all_keys(self, monkeypatch):
        """Returns a dict with expected AI config keys."""
        class FakeAI:
            chat_provider = "groq"
            ollama_url = "http://localhost:11434"
            ollama_model = "llama3"
            groq_api_key = "test-key"
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = "local"
            auto_tag = True
            auto_summarize = True
            tag_confidence_threshold = 0.7
            tag_suggestion_threshold = 0.4
            sync_enrichment = False

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr(factory, "get_settings", lambda: FakeSettings())
        monkeypatch.setattr(factory, "get_ai_overrides_from_db", lambda: {})

        result = factory.get_resolved_ai_config()

        assert isinstance(result, dict)
        assert "chat_provider" in result
        assert result["chat_provider"] == "groq"

    def test_db_overrides_take_precedence(self, monkeypatch):
        """DB overrides are merged and take precedence over env defaults."""
        class FakeAI:
            chat_provider = "groq"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""
            auto_tag = False
            auto_summarize = False
            tag_confidence_threshold = 0.5
            tag_suggestion_threshold = 0.3
            sync_enrichment = False

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr(factory, "get_settings", lambda: FakeSettings())
        monkeypatch.setattr(
            factory, "get_ai_overrides_from_db",
            lambda: {"chat_provider": "ollama", "auto_tag": True}
        )

        result = factory.get_resolved_ai_config()

        assert result["chat_provider"] == "ollama"
        assert result["auto_tag"] is True

    def test_empty_override_values_ignored(self, monkeypatch):
        """Empty string / None overrides do not replace valid env defaults."""
        class FakeAI:
            chat_provider = "groq"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""
            auto_tag = True
            auto_summarize = True
            tag_confidence_threshold = 0.5
            tag_suggestion_threshold = 0.3
            sync_enrichment = False

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr(factory, "get_settings", lambda: FakeSettings())
        monkeypatch.setattr(
            factory, "get_ai_overrides_from_db",
            lambda: {"chat_provider": "", "auto_tag": None}
        )

        result = factory.get_resolved_ai_config()

        assert result["chat_provider"] == "groq"
        assert result["auto_tag"] is True


class TestGetChatProvider:
    """Tests for get_chat_provider()."""

    def test_returns_noop_when_disabled(self, monkeypatch):
        """When chat_provider is empty/None, returns NoOpChatProvider."""
        monkeypatch.setattr(
            factory, "get_resolved_ai_config",
            lambda: {"chat_provider": ""}
        )
        monkeypatch.setattr(factory, "get_settings", lambda: MagicMock())

        provider = factory.get_chat_provider()

        from fourdpocket.ai.base import NoOpChatProvider
        assert isinstance(provider, NoOpChatProvider)

    def test_fallback_to_noop_on_exception(self, monkeypatch):
        """If provider creation raises, falls back to NoOpChatProvider."""
        def raise_on_import(*args, **kwargs):
            raise RuntimeError("Init failed")

        fake_settings = MagicMock()
        fake_settings.ai.chat_provider = "ollama"
        monkeypatch.setattr(factory, "get_settings", lambda: fake_settings)
        monkeypatch.setattr(
            "fourdpocket.ai.openai_compatible.OpenAICompatibleProvider",
            raise_on_import
        )

        provider = factory.get_chat_provider()

        from fourdpocket.ai.base import NoOpChatProvider
        assert isinstance(provider, NoOpChatProvider)


class TestGetEmbeddingProvider:
    """Tests for get_embedding_provider()."""

    def test_returns_local_by_default(self, monkeypatch):
        """Default embedding provider is local via get_local_embedder."""
        class FakeAI:
            embedding_provider = "local"
            nvidia_api_key = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr(factory, "get_settings", lambda: FakeSettings())
        monkeypatch.setattr(factory, "get_ai_overrides_from_db", lambda: {})

        class FakeLocalEmbedder:
            dimensions = 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        monkeypatch.setattr(
            "fourdpocket.ai.local_embeddings.get_local_embedder",
            lambda: FakeLocalEmbedder()
        )

        provider = factory.get_embedding_provider()

        assert provider.dimensions == 384

    def test_nvidia_uses_nvidia_provider(self, monkeypatch):
        """When embedding_provider=nvidia and nvidia_api_key set, uses NvidiaEmbeddingProvider."""
        class FakeAI:
            embedding_provider = "nvidia"
            nvidia_api_key = "nvda-key"

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr(factory, "get_settings", lambda: FakeSettings())
        monkeypatch.setattr(factory, "get_ai_overrides_from_db", lambda: {})

        captured = []

        class FakeNvidiaProvider:
            def __init__(self):
                captured.append(True)

        monkeypatch.setattr(
            "fourdpocket.ai.nvidia_embeddings.NvidiaEmbeddingProvider",
            FakeNvidiaProvider
        )

        factory.get_embedding_provider()

        assert len(captured) == 1

    def test_nvidia_fallback_to_local_on_error(self, monkeypatch):
        """If NVIDIA provider creation fails, falls back to local."""
        class FakeAI:
            embedding_provider = "nvidia"
            nvidia_api_key = "bad-key"

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr(factory, "get_settings", lambda: FakeSettings())
        monkeypatch.setattr(factory, "get_ai_overrides_from_db", lambda: {})

        class FakeLocalEmbedder:
            dimensions = 384

            def embed(self, texts):
                return [[0.1] * 384 for _ in texts]

        def raise_nvidia(*args, **kwargs):
            raise RuntimeError("NVIDIA init failed")

        monkeypatch.setattr(
            "fourdpocket.ai.nvidia_embeddings.NvidiaEmbeddingProvider",
            raise_nvidia
        )
        monkeypatch.setattr(
            "fourdpocket.ai.local_embeddings.get_local_embedder",
            lambda: FakeLocalEmbedder()
        )

        provider = factory.get_embedding_provider()

        assert provider.dimensions == 384


class TestGetAIOverridesFromDB:
    """Tests for get_ai_overrides_from_db()."""

    def test_returns_empty_dict_when_db_unavailable(self, monkeypatch):
        """DB connection failure → empty dict."""
        def raise_no_db(*args, **kwargs):
            raise RuntimeError("No DB")

        monkeypatch.setattr("fourdpocket.db.session.get_engine", raise_no_db)

        result = factory.get_ai_overrides_from_db()

        assert result == {}

    def test_returns_empty_dict_when_no_settings(self, monkeypatch):
        """No InstanceSettings row → empty dict."""
        class FakeSession:
            def get(self, model, id):
                return None

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        def fake_engine():
            return "fake_engine"

        monkeypatch.setattr("fourdpocket.db.session.get_engine", fake_engine)
        # Patch Session at its definition site (fourdpocket.db.session)
        monkeypatch.setattr(
            "fourdpocket.db.session.Session",
            lambda engine: FakeSession()
        )

        result = factory.get_ai_overrides_from_db()

        assert result == {}
