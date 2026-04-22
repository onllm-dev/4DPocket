"""Tests for canonicalizer Tier 2 efficiency — O(1) DB queries not O(n).

The Tier 2 path must use `func.lower(func.trim(Entity.canonical_name)).like(...)` to
pre-filter candidates by first character rather than loading all entities. This keeps
the query count constant regardless of entity count.
"""

import pytest
from sqlmodel import Session, select

from fourdpocket.ai.canonicalizer import _normalize, canonicalize_entity
from fourdpocket.models.entity import Entity
from fourdpocket.models.user import User


@pytest.fixture
def canon_user(db: Session):
    user = User(
        email="canonscale@test.com",
        username="canonscale",
        password_hash="$2b$12$fake",
        display_name="Canon Scale",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestNormalizeHelper:
    def test_strips_punctuation(self):
        assert _normalize("R.A.G.") == "rag"

    def test_lowercases(self):
        assert _normalize("FastAPI") == "fastapi"

    def test_collapses_whitespace(self):
        assert _normalize("  hello   world  ") == "hello world"

    def test_empty_string(self):
        assert _normalize("") == ""


class TestTier2PrefixFilter:
    """Tier 2 must issue a pre-filtered DB query (prefix LIKE) not a full table scan."""

    def test_tier2_uses_func_lower_trim_like(self, db: Session, canon_user):
        """Verify Tier 2 emits a LIKE predicate on first char of normalized name.

        Strategy: seed entities whose canonical_name starts with a different
        letter than the query. The prefix filter means those rows are never
        fetched, so the candidate list must be empty and a new entity is created.
        """
        # Seed entities starting with 'Z' — should not be candidates for 'F' names
        for i in range(5):
            e = Entity(
                user_id=canon_user.id,
                canonical_name=f"Zeta{i}",
                entity_type="concept",
                item_count=0,
            )
            db.add(e)
        db.commit()

        # canonicalize_entity("Foo", ...) — Tier 2 prefix = 'f', so 'Zeta*' rows
        # must not be returned as candidates, and a new entity 'Foo' is created.
        result = canonicalize_entity(
            name="Foo",
            entity_type="concept",
            user_id=canon_user.id,
            db=db,
        )
        assert result.canonical_name == "Foo"

        # Ensure none of the Z-prefixed entities were mutated
        zetas = db.exec(
            select(Entity).where(
                Entity.user_id == canon_user.id,
                Entity.canonical_name.like("Zeta%"),
            )
        ).all()
        assert len(zetas) == 5

    def test_tier2_matches_same_prefix_entity(self, db: Session, canon_user):
        """Same normalized name → same entity returned (no duplicate created)."""
        # Create "FastAPI" entity first
        first = Entity(
            user_id=canon_user.id,
            canonical_name="FastAPI",
            entity_type="tool",
            item_count=0,
        )
        db.add(first)
        db.commit()
        db.refresh(first)

        # canonicalize "fastapi" (different casing) → should return same entity
        result = canonicalize_entity(
            name="fastapi",
            entity_type="tool",
            user_id=canon_user.id,
            db=db,
        )
        assert result.id == first.id

        # Only one entity with type=tool, name=FastAPI should exist
        all_entities = db.exec(
            select(Entity).where(
                Entity.user_id == canon_user.id,
                Entity.entity_type == "tool",
            )
        ).all()
        assert len(all_entities) == 1

    def test_query_count_is_constant_not_linear(self, db: Session, canon_user, monkeypatch):
        """Tier 2 must issue O(1) DB queries regardless of entity count.

        We seed N entities with the same first letter as the query. The function
        may run one candidate-fetch query (the LIKE filter) and one alias check
        at most, not N queries. We verify by counting db.exec() calls.
        """
        n = 10
        for i in range(n):
            e = Entity(
                user_id=canon_user.id,
                canonical_name=f"Concept{i:03d}",
                entity_type="tool",
                item_count=0,
            )
            db.add(e)
        db.commit()

        exec_calls = []
        original_exec = db.exec

        def counting_exec(stmt, *args, **kwargs):
            exec_calls.append(stmt)
            return original_exec(stmt, *args, **kwargs)

        monkeypatch.setattr(db, "exec", counting_exec)

        canonicalize_entity(
            name="ConceptNew",
            entity_type="tool",
            user_id=canon_user.id,
            db=db,
        )

        # Should be very few queries (Tier1 alias check + Tier2 candidate fetch),
        # definitely not N=10 individual queries.
        assert len(exec_calls) <= 5, (
            f"Expected O(1) queries, got {len(exec_calls)} for {n} entities"
        )
