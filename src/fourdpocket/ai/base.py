"""AI provider protocol definitions."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ChatProvider(Protocol):
    """Protocol for chat/completion AI providers."""

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate text from a prompt."""
        ...

    def generate_json(self, prompt: str, system_prompt: str = "") -> dict:
        """Generate structured JSON output."""
        ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        ...

    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        ...


class NoOpChatProvider:
    """No-op provider when AI is disabled or unavailable."""

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        return ""

    def generate_json(self, prompt: str, system_prompt: str = "") -> dict:
        return {}
