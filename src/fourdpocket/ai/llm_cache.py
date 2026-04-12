"""LLM response caching — hash-based dedup for extraction, summary, tagging calls."""

import hashlib
import json
import logging

from sqlmodel import Session, select

from fourdpocket.models.llm_cache import LLMCache

logger = logging.getLogger(__name__)


def _hash_content(text: str, cache_type: str, model_name: str = "") -> str:
    """Generate a stable hash for cache lookup."""
    key = f"{cache_type}:{model_name}:{text}"
    return hashlib.sha256(key.encode()).hexdigest()


def get_cached_response(
    db: Session,
    text: str,
    cache_type: str,
    model_name: str = "",
) -> dict | None:
    """Look up a cached LLM response. Returns parsed JSON or None."""
    content_hash = _hash_content(text, cache_type, model_name)
    row = db.exec(
        select(LLMCache).where(
            LLMCache.content_hash == content_hash,
            LLMCache.cache_type == cache_type,
        )
    ).first()

    if row is None:
        return None

    try:
        return json.loads(row.response)
    except (json.JSONDecodeError, TypeError):
        return None


def store_cached_response(
    db: Session,
    text: str,
    cache_type: str,
    response: dict | list,
    model_name: str = "",
) -> None:
    """Store an LLM response in the cache."""
    content_hash = _hash_content(text, cache_type, model_name)

    # Upsert: check if exists first
    existing = db.exec(
        select(LLMCache).where(
            LLMCache.content_hash == content_hash,
            LLMCache.cache_type == cache_type,
        )
    ).first()

    if existing:
        existing.response = json.dumps(response)
        existing.model_name = model_name
        db.add(existing)
    else:
        row = LLMCache(
            content_hash=content_hash,
            cache_type=cache_type,
            response=json.dumps(response),
            model_name=model_name,
        )
        db.add(row)

    db.flush()
