"""Sanitize user content before passing to LLM prompts."""

import re

# Patterns commonly used in prompt injection attacks
_INJECTION_PATTERNS = [
    r'(?i)(ignore|disregard|forget|override)\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions?|prompts?|context|rules?|guidelines?)',
    r'(?i)you\s+are\s+now\s+(a|an|in)\s+',
    r'(?i)new\s+instructions?\s*:',
    r'(?i)system\s*:\s*',
    r'(?i)<\/?system>',
    r'(?i)```\s*(system|instruction|prompt)',
]

_COMPILED_PATTERNS = [re.compile(p) for p in _INJECTION_PATTERNS]


def sanitize_for_prompt(text: str, max_length: int = 4000) -> str:
    """Sanitize user-provided text before including in an LLM prompt.

    - Truncates to max_length to prevent context stuffing
    - Strips common prompt injection patterns
    - Returns cleaned text wrapped in XML delimiters for clear boundaries
    """
    if not text:
        return ""

    text = text[:max_length]

    for pattern in _COMPILED_PATTERNS:
        text = pattern.sub("[content filtered]", text)

    return text


def wrap_user_content(text: str, label: str = "content") -> str:
    """Wrap sanitized user text in XML delimiters for LLM prompt boundaries."""
    cleaned = sanitize_for_prompt(text)
    return f"<user_{label}>\n{cleaned}\n</user_{label}>"
