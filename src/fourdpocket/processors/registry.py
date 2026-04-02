"""Processor registry — URL pattern matching and processor discovery."""

import re

from fourdpocket.processors.base import BaseProcessor

_REGISTRY: dict[str, type[BaseProcessor]] = {}
_PATTERNS: list[tuple[re.Pattern, str, int]] = []
_COMPILED = False


def register_processor(cls: type[BaseProcessor]) -> type[BaseProcessor]:
    """Decorator to register a processor class."""
    name = cls.__name__
    _REGISTRY[name] = cls

    for pattern in cls.url_patterns:
        compiled = re.compile(pattern, re.IGNORECASE)
        _PATTERNS.append((compiled, name, cls.priority))

    # Re-sort by priority (highest first)
    _PATTERNS.sort(key=lambda x: x[2], reverse=True)

    return cls


def match_processor(url: str) -> BaseProcessor:
    """Find the best processor for a URL. Falls back to GenericURLProcessor."""
    for compiled_pattern, name, _priority in _PATTERNS:
        if compiled_pattern.search(url):
            return _REGISTRY[name]()

    # Fallback to generic
    if "GenericURLProcessor" in _REGISTRY:
        return _REGISTRY["GenericURLProcessor"]()

    raise ValueError(f"No processor found for URL: {url}")


def get_processor(name: str) -> BaseProcessor:
    """Get a processor by class name."""
    if name not in _REGISTRY:
        raise KeyError(f"Processor not found: {name}")
    return _REGISTRY[name]()


def list_processors() -> list[str]:
    """List all registered processor names."""
    return list(_REGISTRY.keys())
