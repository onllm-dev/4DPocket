"""Chat provider - works with OpenAI-compatible and Anthropic-compatible endpoints."""

import json
import logging

from openai import OpenAI

from fourdpocket.config import get_settings

logger = logging.getLogger(__name__)

PROVIDER_CONFIGS = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "default_model": "llama3.2",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "qwen/qwen3.5-397b-a17b",
    },
    "custom": {
        "base_url": "",
        "default_model": "",
    },
}


class OpenAICompatibleProvider:
    """Chat provider using OpenAI SDK with configurable base_url.

    Supports both OpenAI-compatible and Anthropic-compatible API formats.
    """

    def __init__(self, provider: str | None = None, overrides: dict | None = None):
        settings = get_settings()
        ov = overrides or {}
        provider = ov.get("chat_provider") or provider or settings.ai.chat_provider
        config = PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS["ollama"])

        self._api_type = "openai"  # default for all built-in providers
        base_url = config["base_url"]

        if provider == "ollama":
            base_url = f"{settings.ai.ollama_url}/v1"
            api_key = "ollama"
            self._model = settings.ai.ollama_model
        elif provider == "groq":
            api_key = ov.get("groq_api_key") or settings.ai.groq_api_key
            self._model = config["default_model"]
        elif provider == "nvidia":
            api_key = ov.get("nvidia_api_key") or settings.ai.nvidia_api_key
            self._model = config["default_model"]
        elif provider == "custom":
            base_url = ov.get("custom_base_url") or settings.ai.custom_base_url
            api_key = ov.get("custom_api_key") or settings.ai.custom_api_key
            self._model = ov.get("custom_model") or settings.ai.custom_model
            self._api_type = ov.get("custom_api_type") or settings.ai.custom_api_type
            if not base_url or not api_key:
                raise ValueError("Custom provider requires base_url and api_key")
        else:
            api_key = "none"
            self._model = config.get("default_model", "llama3.2")

        self._provider = provider

        if self._api_type == "anthropic":
            self._anthropic_base_url = base_url
            self._anthropic_api_key = api_key
            self._client = None
        else:
            self._client = OpenAI(base_url=base_url, api_key=api_key)

    def _call_anthropic(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        """Call Anthropic-compatible API using httpx (no SDK dependency)."""
        import httpx

        # Anthropic uses a different message format
        system_text = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text = msg["content"]
            else:
                user_messages.append(msg)

        payload = {
            "model": self._model,
            "messages": user_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_text:
            payload["system"] = system_text

        headers = {
            "x-api-key": self._anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        try:
            resp = httpx.post(
                f"{self._anthropic_base_url.rstrip('/')}/messages",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            # Anthropic returns content as array of blocks
            content_blocks = data.get("content", [])
            return "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        except Exception as e:
            logger.warning("Anthropic API call failed (%s): %s", self._provider, e)
            return ""

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate text completion."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self._api_type == "anthropic":
            return self._call_anthropic(messages, temperature=0.3, max_tokens=2000)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
                timeout=30,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning("Chat generation failed (%s): %s", self._provider, e)
            return ""

    def generate_json(self, prompt: str, system_prompt: str = "") -> dict:
        """Generate structured JSON output."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        if self._api_type == "anthropic":
            content = self._call_anthropic(messages, temperature=0.1, max_tokens=2000)
            return _parse_json(content)

        try:
            kwargs = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 2000,
                "timeout": 30,
            }
            # Groq, NVIDIA, and some custom providers support response_format
            if self._provider in ("groq", "nvidia") or (
                self._provider == "custom" and self._api_type == "openai"
            ):
                kwargs["response_format"] = {"type": "json_object"}

            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or "{}"
            return _parse_json(content)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse failed: %s", e)
            return {}
        except Exception as e:
            logger.warning("JSON generation failed (%s): %s", self._provider, e)
            return {}


def _parse_json(content: str) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning("JSON parse failed for content: %s", content[:200])
        return {}
