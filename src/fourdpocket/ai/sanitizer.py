"""Sanitize user content before passing to LLM prompts."""

import base64
import re

# Patterns commonly used in prompt injection attacks
_INJECTION_PATTERNS = [
    r'(?i)(ignore|disregard|forget|override)\s+(all\s+)?(previous|above|prior|earlier)\s+(instructions?|prompts?|context|rules?|guidelines?)',
    r'(?i)you\s+are\s+now\s+(a|an|in)\s+',
    r'(?i)new\s+instructions?\s*:',
    r'(?i)system\s*:\s*',
    r'(?i)<\/?system>',
    r'(?i)```\s*(system|instruction|prompt)',
    r'(?i)act\s+as\s+(a|an)\s+',
    r'(?i)pretend\s+you\s+are',
    r'(?i)role:\s*',
    r'(?i)instruct\s+',
    r'(?i)developer\s+mode',
    # Base64-encoded injection attempts
    r'(?i)[A-Za-z0-9+/]{50,}={0,2}',  # long base64 strings - suspicious
]

_COMPILED_PATTERNS = [re.compile(p) for p in _INJECTION_PATTERNS]


def sanitize_for_prompt(text: str, max_length: int = 4000) -> str:
    """Sanitize user-provided text before including in an LLM prompt.

    - Truncates to max_length to prevent context stuffing
    - Strips common prompt injection patterns
    - Detects base64-encoded payloads
    - Returns cleaned text wrapped in XML delimiters for clear boundaries
    """
    if not text:
        return ""

    text = text[:max_length]

    for pattern in _COMPILED_PATTERNS:
        text = pattern.sub("[content filtered]", text)

    # Check for base64-encoded injection in suspiciously formatted strings
    try:
        decoded = base64.b64decode(text.encode()).decode("utf-8", errors="ignore")
        if any(kw in decoded.lower() for kw in ["ignore", "system", "prompt", "instruction"]):
            return "[content filtered]"
    except Exception:
        pass

    return text


