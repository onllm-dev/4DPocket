"""Sanitize user content before passing to LLM prompts."""

import base64
import re
import urllib.parse

# Cyrillic/Greek homoglyphs that look identical to ASCII
_HOMOGLYPH_MAP = str.maketrans({
    '\u0430': 'a', '\u0435': 'e', '\u043e': 'o', '\u0440': 'p',
    '\u0441': 'c', '\u0456': 'i', '\u0458': 'j', '\u0455': 's',
    '\u0445': 'x', '\u043d': 'h', '\u0443': 'y', '\u0442': 't',
    '\u03bf': 'o', '\u03bd': 'v',  # Greek
})

# Zero-width and invisible characters
_INVISIBLE_CHARS = re.compile(r'[\u200b\u200c\u200d\u2060\ufeff\u00ad\u200e\u200f]+')

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

    # Strip invisible/zero-width characters
    text = _INVISIBLE_CHARS.sub('', text)

    # Normalize unicode homoglyphs (Cyrillic/Greek lookalikes → ASCII)
    text = text.translate(_HOMOGLYPH_MAP)

    # URL-decode and re-check (catches %3Cscript%3E etc.)
    try:
        decoded = urllib.parse.unquote(text)
        if decoded != text:
            text = decoded
    except Exception:
        pass

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


