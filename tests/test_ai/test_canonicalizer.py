"""Tests for entity canonicalization."""

import pytest
from sqlmodel import Session, select

from fourdpocket.ai.canonicalizer import canonicalize_entity
from fourdpocket.models.entity import Entity, EntityAlias
from fourdpocket.models.user import User


@pytest.fixture
def canon_user(db: Session):
    user = User(
        email="canon@example.com",
        username="canonuser",
        password_hash="$2b$12$fakehash",
        display_name="Canon User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestCanonicalize:
    def test_creates_new_entity(self, db: Session, canon_user):
        entity = canonicalize_entity("FastAPI", "tool", canon_user.id, db)
        assert entity.canonical_name == "FastAPI"
        assert entity.entity_type == "tool"
        assert entity.user_id == canon_user.id

        # Alias should be created
        aliases = db.exec(
            select(EntityAlias).where(EntityAlias.entity_id == entity.id)
        ).all()
        assert len(aliases) == 1
        assert aliases[0].alias == "FastAPI"

    def test_exact_alias_match(self, db: Session, canon_user):
        e1 = canonicalize_entity("FastAPI", "tool", canon_user.id, db)
        e2 = canonicalize_entity("FastAPI", "tool", canon_user.id, db)
        assert e1.id == e2.id

    def test_normalized_match(self, db: Session, canon_user):
        e1 = canonicalize_entity("FastAPI", "tool", canon_user.id, db)
        e2 = canonicalize_entity("fastapi", "tool", canon_user.id, db)
        assert e1.id == e2.id

        # New alias should be added
        aliases = db.exec(
            select(EntityAlias).where(EntityAlias.entity_id == e1.id)
        ).all()
        alias_names = {a.alias for a in aliases}
        assert "FastAPI" in alias_names
        assert "fastapi" in alias_names

    def test_punctuation_normalized(self, db: Session, canon_user):
        e1 = canonicalize_entity("R.A.G.", "concept", canon_user.id, db)
        e2 = canonicalize_entity("RAG", "concept", canon_user.id, db)
        assert e1.id == e2.id

    def test_different_types_not_merged(self, db: Session, canon_user):
        e1 = canonicalize_entity("Python", "tool", canon_user.id, db)
        e2 = canonicalize_entity("Python", "concept", canon_user.id, db)
        assert e1.id != e2.id

    def test_user_scoping(self, db: Session, canon_user):
        other_user = User(
            email="other@example.com",
            username="otheruser",
            password_hash="$2b$12$fakehash",
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        e1 = canonicalize_entity("FastAPI", "tool", canon_user.id, db)
        e2 = canonicalize_entity("FastAPI", "tool", other_user.id, db)
        assert e1.id != e2.id

    def test_description_stored(self, db: Session, canon_user):
        entity = canonicalize_entity(
            "LangChain", "tool", canon_user.id, db,
            description="Framework for LLM apps",
        )
        assert entity.description == "Framework for LLM apps"

    def test_idempotent(self, db: Session, canon_user):
        for _ in range(3):
            canonicalize_entity("Docker", "tool", canon_user.id, db)

        entities = db.exec(
            select(Entity).where(
                Entity.user_id == canon_user.id,
                Entity.canonical_name == "Docker",
            )
        ).all()
        assert len(entities) == 1
