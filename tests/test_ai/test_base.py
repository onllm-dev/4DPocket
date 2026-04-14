"""Tests for ai/base.py — ChatProvider and EmbeddingProvider protocols."""

from fourdpocket.ai.base import (
    ChatProvider,
    EmbeddingProvider,
    NoOpChatProvider,
)


class TestNoOpChatProvider:
    """Tests for NoOpChatProvider."""

    def test_generate_returns_empty_string(self):
        """generate() always returns empty string."""
        provider = NoOpChatProvider()
        result = provider.generate("any prompt")
        assert result == ""

    def test_generate_with_system_prompt(self):
        """generate() ignores system_prompt and returns empty string."""
        provider = NoOpChatProvider()
        result = provider.generate("user prompt", system_prompt="You are a helpful assistant.")
        assert result == ""

    def test_generate_json_returns_empty_dict(self):
        """generate_json() always returns empty dict."""
        provider = NoOpChatProvider()
        result = provider.generate_json("any prompt")
        assert result == {}


class TestChatProviderProtocol:
    """Tests for ChatProvider protocol compliance."""

    def test_noop_is_chat_provider(self):
        """NoOpChatProvider satisfies ChatProvider protocol."""
        provider = NoOpChatProvider()
        assert isinstance(provider, ChatProvider)

    def test_generate_json_method_exists(self):
        """ChatProvider must have generate_json() method."""
        assert hasattr(ChatProvider, "generate_json")


class TestEmbeddingProviderProtocol:
    """Tests for EmbeddingProvider protocol compliance."""
    pass
