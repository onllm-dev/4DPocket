"""Tests for ai/openai_compatible.py — OpenAI-compatible chat provider."""

from unittest.mock import MagicMock, patch

import pytest


class TestOpenAICompatibleProviderInit:
    """Tests for OpenAICompatibleProvider.__init__()."""

    def test_ollama_sets_correct_base_url(self, monkeypatch):
        """Ollama provider uses settings.ai.ollama_url for base URL."""
        class FakeAI:
            chat_provider = "ollama"
            ollama_url = "http://localhost:11434"
            ollama_model = "llama3.2"
            ollama_api_key = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai:
            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="ollama")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args.kwargs
            assert "base_url" in call_kwargs
            assert "11434" in call_kwargs["base_url"]

    def test_groq_uses_groq_base_url(self, monkeypatch):
        """Groq provider uses groq config base URL."""
        class FakeAI:
            chat_provider = "groq"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = "groq-test-key"
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai:
            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="groq")
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args.kwargs
            assert "api_key" in call_kwargs
            assert call_kwargs["api_key"] == "groq-test-key"

    def test_nvidia_sets_nvidia_base_url(self, monkeypatch):
        """NVIDIA provider uses NVIDIA config base URL."""
        class FakeAI:
            chat_provider = "nvidia"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = ""
            nvidia_api_key = "nvda-test-key"
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai:
            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="nvidia")
            mock_openai.assert_called_once()

    def test_custom_with_anthropic_api_type(self, monkeypatch):
        """Custom provider with anthropic api_type sets _api_type correctly."""
        class FakeAI:
            chat_provider = "custom"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = "https://api.anthropic.com"
            custom_api_key = "anthropic-key"
            custom_model = "claude-3-5-sonnet"
            custom_api_type = "anthropic"
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(provider="custom")

        assert provider._api_type == "anthropic"
        assert provider._anthropic_base_url == "https://api.anthropic.com"
        assert provider._anthropic_api_key == "anthropic-key"
        assert provider._client is None

    def test_custom_missing_base_url_raises(self, monkeypatch):
        """Custom provider without base_url raises ValueError."""
        class FakeAI:
            chat_provider = "custom"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = "some-key"
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
        with pytest.raises(ValueError, match="base_url"):
            OpenAICompatibleProvider(provider="custom")


class TestGenerate:
    """Tests for generate() method."""

    def test_generate_calls_openai_api(self, monkeypatch):
        """generate() calls OpenAI chat completions API with correct model and messages."""
        class FakeAI:
            chat_provider = "groq"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = "test-key"
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Hello world"))]

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="groq")
            result = provider.generate("Say hello")

            mock_client.chat.completions.create.assert_called_once()
            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            assert call_kwargs["model"] == "llama-3.3-70b-versatile"
            assert call_kwargs["temperature"] == 0.3
            assert call_kwargs["max_tokens"] == 2000
            assert call_kwargs["timeout"] == 30
            # Check messages structure
            msgs = call_kwargs["messages"]
            assert any(m["role"] == "user" and m["content"] == "Say hello" for m in msgs)

            assert result == "Hello world"

    def test_generate_with_system_prompt(self, monkeypatch):
        """generate() prepends system message when system_prompt is provided."""
        class FakeAI:
            chat_provider = "ollama"
            ollama_url = "http://localhost:11434"
            ollama_model = "llama3.2"
            ollama_api_key = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Response"))]

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="ollama")
            result = provider.generate("User prompt", system_prompt="You are helpful.")

            call_kwargs = mock_client.chat.completions.create.call_args.kwargs
            msgs = call_kwargs["messages"]
            assert msgs[0]["role"] == "system"
            assert msgs[0]["content"] == "You are helpful."
            assert msgs[1]["role"] == "user"
            assert msgs[1]["content"] == "User prompt"

            assert result == "Response"

    def test_generate_api_error_returns_empty(self, monkeypatch):
        """generate() returns empty string when OpenAI API raises an exception."""
        class FakeAI:
            chat_provider = "groq"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = "test-key"
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(side_effect=Exception("API error"))
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="groq")
            result = provider.generate("Test prompt")

            assert result == ""

    def test_generate_timeout_returns_empty(self, monkeypatch):
        """generate() returns empty string on timeout."""
        class FakeAI:
            chat_provider = "ollama"
            ollama_url = "http://localhost:11434"
            ollama_model = "llama3.2"
            ollama_api_key = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        import httpx
        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(
                side_effect=httpx.TimeoutException("timed out")
            )
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="ollama")
            result = provider.generate("Slow prompt")

            assert result == ""

    def test_generate_null_content_returns_empty(self, monkeypatch):
        """generate() returns empty string when message content is None."""
        class FakeAI:
            chat_provider = "groq"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = "test-key"
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=None))]

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="groq")
            result = provider.generate("Test")

            assert result == ""


class TestGenerateJSON:
    """Tests for generate_json() method."""

    def test_generate_json_parses_response(self, monkeypatch):
        """generate_json() parses JSON response and returns dict."""
        class FakeAI:
            chat_provider = "ollama"
            ollama_url = "http://localhost:11434"
            ollama_model = "llama3.2"
            ollama_api_key = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"key": "value"}'))]

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="ollama")
            result = provider.generate_json("Return JSON")

            assert result == {"key": "value"}

    def test_generate_json_with_code_block(self, monkeypatch):
        """generate_json() strips markdown code fences before parsing."""
        class FakeAI:
            chat_provider = "ollama"
            ollama_url = "http://localhost:11434"
            ollama_model = "llama3.2"
            ollama_api_key = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='```json\n{"tags": ["a", "b"]}\n```'))
        ]

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="ollama")
            result = provider.generate_json("Return JSON")

            assert result == {"tags": ["a", "b"]}

    def test_generate_json_invalid_returns_empty_dict(self, monkeypatch):
        """generate_json() returns empty dict on JSON parse failure."""
        class FakeAI:
            chat_provider = "ollama"
            ollama_url = "http://localhost:11434"
            ollama_model = "llama3.2"
            ollama_api_key = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="not valid json"))]

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="ollama")
            result = provider.generate_json("Return JSON")

            assert result == {}

    def test_generate_json_api_error_returns_empty_dict(self, monkeypatch):
        """generate_json() returns empty dict when API raises an exception."""
        class FakeAI:
            chat_provider = "ollama"
            ollama_url = "http://localhost:11434"
            ollama_model = "llama3.2"
            ollama_api_key = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = ""
            custom_api_key = ""
            custom_model = ""
            custom_api_type = ""
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        with patch("fourdpocket.ai.openai_compatible.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = MagicMock(side_effect=Exception("API error"))
            mock_openai_cls.return_value = mock_client

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="ollama")
            result = provider.generate_json("Return JSON")

            assert result == {}


class TestAnthropicPath:
    """Tests for the Anthropic-compatible code path."""

    def test_generate_uses_anthropic_path(self, monkeypatch):
        """When _api_type=anthropic, generate() calls _call_anthropic()."""
        class FakeAI:
            chat_provider = "custom"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = "https://api.anthropic.com"
            custom_api_key = "anthropic-key"
            custom_model = "claude-3-5-sonnet"
            custom_api_type = "anthropic"
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Anthropic response"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response) as mock_post:
            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="custom")
            result = provider.generate("User prompt", system_prompt="You are helpful.")

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["headers"]["x-api-key"] == "anthropic-key"
            assert call_kwargs["headers"]["anthropic-version"] == "2023-06-01"
            assert result == "Anthropic response"

    def test_anthropic_path_error_returns_empty(self, monkeypatch):
        """Anthropic path returns empty string on API error."""
        class FakeAI:
            chat_provider = "custom"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = "https://api.anthropic.com"
            custom_api_key = "anthropic-key"
            custom_model = "claude-3-5-sonnet"
            custom_api_type = "anthropic"
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        import respx
        from httpx import Response

        with respx.mock(assert_all_called=False):
            mock_route = respx.post("https://api.anthropic.com/messages").mock(
                return_value=Response(500, json={"error": "internal error"})
            )

            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="custom")
            result = provider.generate("Test")

            assert result == ""

    def test_generate_json_uses_anthropic_path(self, monkeypatch):
        """generate_json() uses Anthropic path when api_type=anthropic."""
        class FakeAI:
            chat_provider = "custom"
            ollama_url = ""
            ollama_model = ""
            groq_api_key = ""
            nvidia_api_key = ""
            custom_base_url = "https://api.anthropic.com"
            custom_api_key = "anthropic-key"
            custom_model = "claude-3-5-sonnet"
            custom_api_type = "anthropic"
            embedding_provider = "local"
            embedding_model = ""

        class FakeSettings:
            ai = FakeAI()

        monkeypatch.setattr("fourdpocket.ai.openai_compatible.get_settings", lambda: FakeSettings())

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": '{"result": "ok"}'}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response) as mock_post:
            from fourdpocket.ai.openai_compatible import OpenAICompatibleProvider
            provider = OpenAICompatibleProvider(provider="custom")
            result = provider.generate_json("Return JSON")

            mock_post.assert_called_once()
            assert result == {"result": "ok"}


class TestParseJSON:
    """Tests for _parse_json() helper."""

    def test_parse_json_plain(self, monkeypatch):
        """_parse_json() parses plain JSON string."""
        from fourdpocket.ai.openai_compatible import _parse_json

        result = _parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_with_code_block(self, monkeypatch):
        """_parse_json() strips markdown code fences."""
        from fourdpocket.ai.openai_compatible import _parse_json

        result = _parse_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_invalid_returns_empty(self, monkeypatch):
        """_parse_json() returns empty dict on parse failure."""
        from fourdpocket.ai.openai_compatible import _parse_json

        result = _parse_json("not json at all")
        assert result == {}

    def test_parse_json_empty_content(self, monkeypatch):
        """_parse_json() handles empty content."""
        from fourdpocket.ai.openai_compatible import _parse_json

        result = _parse_json("")
        assert result == {}
