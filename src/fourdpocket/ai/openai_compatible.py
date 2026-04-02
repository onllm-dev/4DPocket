"""OpenAI-compatible chat provider — works with Ollama, Groq, and NVIDIA."""

import json
import logging

from openai import OpenAI

from fourdpocket.config import get_settings

logger = logging.getLogger(__name__)

PROVIDER_CONFIGS = {
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",  # Ollama doesn't need a real key
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
}


class OpenAICompatibleProvider:
    """Chat provider using OpenAI SDK with configurable base_url."""

    def __init__(self, provider: str | None = None):
        settings = get_settings()
        provider = provider or settings.ai.chat_provider
        config = PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS["ollama"])

        base_url = config["base_url"]
        if provider == "ollama":
            base_url = f"{settings.ai.ollama_url}/v1"
            api_key = "ollama"
            self._model = settings.ai.ollama_model
        elif provider == "groq":
            api_key = settings.ai.groq_api_key
            self._model = config["default_model"]
        elif provider == "nvidia":
            api_key = settings.ai.nvidia_api_key
            self._model = config["default_model"]
        else:
            api_key = "none"
            self._model = config.get("default_model", "llama3.2")

        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self._provider = provider

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate text completion."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

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

        try:
            kwargs = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 2000,
                "timeout": 30,
            }
            # Groq and NVIDIA support response_format
            if self._provider in ("groq", "nvidia"):
                kwargs["response_format"] = {"type": "json_object"}

            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or "{}"

            # Parse JSON from response, handling markdown code blocks
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0]

            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse failed: %s", e)
            return {}
        except Exception as e:
            logger.warning("JSON generation failed (%s): %s", self._provider, e)
            return {}
