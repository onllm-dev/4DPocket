"""AI-powered title generation for notes."""

import logging

from fourdpocket.ai.factory import get_chat_provider
from fourdpocket.ai.sanitizer import sanitize_for_prompt

logger = logging.getLogger(__name__)

TITLE_SYSTEM_PROMPT = """You are a concise title generator. Given the content of a note, generate a clear, descriptive title in 5-10 words. Return ONLY the title text, nothing else."""


def generate_title(content: str) -> str | None:
    """Generate a title from note content using the configured AI provider."""
    if not content:
        return None

    chat = get_chat_provider()

    sanitized = sanitize_for_prompt(content, max_length=2000)
    prompt = (
        "Generate a concise title for the following note content.\n\n"
        f"<user_content>\n{sanitized}\n</user_content>"
    )
    result = chat.generate(prompt, system_prompt=TITLE_SYSTEM_PROMPT)

    if result:
        # Cap length to prevent LLM producing excessively long titles
        return result.strip()[:200]
    return None
