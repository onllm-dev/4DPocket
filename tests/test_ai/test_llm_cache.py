"""Tests for ai/llm_cache.py."""

import json

from sqlmodel import Session, select

from fourdpocket.ai import llm_cache
from fourdpocket.models.llm_cache import LLMCache
from fourdpocket.models.user import User


def _user(db: Session, email: str = "cache@test.com") -> User:
    u = User(email=email, username=email.split("@")[0], password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ─── _hash_content ───────────────────────────────────────────────────────────


def test_hash_content_deterministic():
    """Same inputs produce the same hash."""
    h1 = llm_cache._hash_content("hello world", "summary", "gpt-4")
    h2 = llm_cache._hash_content("hello world", "summary", "gpt-4")
    assert h1 == h2


def test_hash_content_differs_by_text():
    """Different text → different hash."""
    h1 = llm_cache._hash_content("hello", "summary", "gpt-4")
    h2 = llm_cache._hash_content("world", "summary", "gpt-4")
    assert h1 != h2


def test_hash_content_differs_by_cache_type():
    """Same text, different cache_type → different hash."""
    h1 = llm_cache._hash_content("hello", "summary", "gpt-4")
    h2 = llm_cache._hash_content("hello", "extraction", "gpt-4")
    assert h1 != h2


def test_hash_content_differs_by_model():
    """Same text and cache_type, different model → different hash."""
    h1 = llm_cache._hash_content("hello", "summary", "gpt-4")
    h2 = llm_cache._hash_content("hello", "summary", "claude-3")
    assert h1 != h2


# ─── get_cached_response ──────────────────────────────────────────────────────


def test_cache_hit_returns_cached(db):
    """Same content hash → cached response is returned."""
    content = "Lorem ipsum dolor sit amet"
    cache_type = "summary"
    model_name = "gpt-4"
    cached_data = {"summary": "A filler summary.", "confidence": "high"}

    # Store it
    llm_cache.store_cached_response(
        db, content, cache_type, cached_data, model_name
    )

    # Retrieve it
    result = llm_cache.get_cached_response(db, content, cache_type, model_name)

    assert result == cached_data


def test_cache_miss_returns_none(db):
    """New content hash → None (provider should be called)."""
    result = llm_cache.get_cached_response(
        db, "never seen before content", "summary", "gpt-4"
    )
    assert result is None


def test_cache_key_includes_operation(db):
    """Same content, different operation → different cache key."""
    content = "Shared content"
    model = "gpt-4"

    llm_cache.store_cached_response(
        db, content, "summary", {"text": "summary text"}, model
    )

    # Same content but different cache_type → cache miss
    result = llm_cache.get_cached_response(
        db, content, "extraction", model
    )
    assert result is None


def test_cache_hit_different_model(db):
    """Same content but different model → separate cache entries."""
    content = "Same content"
    cache_type = "summary"

    llm_cache.store_cached_response(
        db, content, cache_type, {"text": "from gpt"}, "gpt-4"
    )

    result = llm_cache.get_cached_response(
        db, content, cache_type, "claude-3"
    )
    assert result is None  # different model → cache miss


def test_cache_corrupt_json_returns_none(db):
    """If stored JSON is corrupt, get_cached_response returns None."""
    content = "corrupt json test"
    cache_type = "summary"

    content_hash = llm_cache._hash_content(content, cache_type, "")
    row = LLMCache(
        content_hash=content_hash,
        cache_type=cache_type,
        response="not valid json {",
        model_name="",
    )
    db.add(row)
    db.commit()

    result = llm_cache.get_cached_response(db, content, cache_type, "")

    assert result is None


# ─── store_cached_response ───────────────────────────────────────────────────


def test_store_upserts_existing(db):
    """Storing the same content+type updates the existing row."""
    content = "Upsert test content"
    cache_type = "summary"
    model = "gpt-4"

    # First store
    llm_cache.store_cached_response(
        db, content, cache_type, {"text": "original"}, model
    )
    rows_before = db.exec(
        select(LLMCache).where(LLMCache.content_hash == llm_cache._hash_content(content, cache_type, model))
    ).all()
    assert len(rows_before) == 1

    # Second store (upsert)
    llm_cache.store_cached_response(
        db, content, cache_type, {"text": "updated"}, model
    )

    rows_after = db.exec(
        select(LLMCache).where(LLMCache.content_hash == llm_cache._hash_content(content, cache_type, model))
    ).all()
    assert len(rows_after) == 1
    parsed = json.loads(rows_after[0].response)
    assert parsed == {"text": "updated"}


def test_store_creates_new_row(db):
    """New content+type combination creates a new row."""
    content = "Brand new content xyz123"
    cache_type = "extraction"
    model = "gpt-4"

    llm_cache.store_cached_response(
        db, content, cache_type, {"entities": []}, model
    )

    row = db.exec(
        select(LLMCache).where(
            LLMCache.content_hash == llm_cache._hash_content(content, cache_type, model)
        )
    ).first()

    assert row is not None
    assert row.cache_type == cache_type


def test_store_serializes_list(db):
    """Response can be a list (not just a dict)."""
    content = "List response test"
    cache_type = "keywords"

    llm_cache.store_cached_response(db, content, cache_type, ["tag1", "tag2", "tag3"], "")

    result = llm_cache.get_cached_response(db, content, cache_type, "")

    assert result == ["tag1", "tag2", "tag3"]
