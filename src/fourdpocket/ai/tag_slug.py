"""Canonical tag slug normalizer shared by api/tags.py and ai/tagger.py."""

import re


def normalize_tag_slug(name: str) -> str:
    """Normalise a tag name into a slug.

    Allows forward-slashes so AI-generated hierarchical tags like ``ai/ml``
    are preserved intact.  Strips all other non-word, non-space, non-hyphen
    characters, collapses whitespace runs to a single hyphen, and lower-cases
    the result.  Length is capped at 100 characters to prevent DoS.
    """
    slug = name.lower().strip()[:100]
    slug = re.sub(r"[^\w\s/-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug
