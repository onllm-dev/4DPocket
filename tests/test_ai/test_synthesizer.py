"""Entity synthesis tests."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from fourdpocket.ai import synthesizer as synth
from fourdpocket.models.entity import Entity, ItemEntity
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.user import User


class _FakeChat:
    """Deterministic chat stub returning a valid synthesis JSON."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def generate(self, prompt: str, system_prompt: str = "") -> str:  # noqa: ARG002
        return ""

    def generate_json(self, prompt: str, system_prompt: str = "") -> dict:  # noqa: ARG002
        self.calls += 1
        return self.payload


def _user(db: Session, email: str = "syn@x.com") -> User:
    u = User(email=email, username=email.split("@")[0], password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _item(db: Session, user_id: uuid.UUID, title: str) -> KnowledgeItem:
    it = KnowledgeItem(
        user_id=user_id,
        title=title,
        content=f"discussion about {title}",
        item_type="note",
        source_platform="generic",
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


def _entity(
    db: Session, user_id: uuid.UUID, name: str = "FastAPI", item_count: int = 3
) -> Entity:
    ent = Entity(
        user_id=user_id,
        canonical_name=name,
        entity_type="tool",
        description="short description",
        item_count=item_count,
    )
    db.add(ent)
    db.commit()
    db.refresh(ent)
    return ent


def _link_items(db: Session, entity_id: uuid.UUID, item_ids: list[uuid.UUID]) -> None:
    for iid in item_ids:
        db.add(
            ItemEntity(
                item_id=iid,
                entity_id=entity_id,
                chunk_id=None,
                salience=0.6,
                context=f"context-{iid}",
            )
        )
    db.commit()


# ─── synthesize_entity happy path ─────────────────────────────────────────


def test_synthesize_generates_valid_payload(db, monkeypatch):
    user = _user(db)
    items = [_item(db, user.id, f"article-{i}") for i in range(3)]
    entity = _entity(db, user.id)
    _link_items(db, entity.id, [i.id for i in items])

    fake = _FakeChat(
        {
            "summary": "FastAPI is a modern Python web framework.",
            "themes": ["async", "pydantic"],
            "key_contexts": [
                {"context": "Used for APIs.", "source_item_id": str(items[0].id)}
            ],
            "relationships": [
                {"entity_name": "Starlette", "nature": "Built on top of."}
            ],
            "confidence": "high",
        }
    )
    monkeypatch.setattr(synth, "get_chat_provider", lambda: fake)

    result = synth.synthesize_entity(entity.id, db)
    assert result is not None
    assert result["summary"].startswith("FastAPI")
    assert result["confidence"] == "high"
    assert result["source_item_count"] == 3
    assert len(result["themes"]) == 2

    db.refresh(entity)
    assert entity.synthesis is not None
    assert entity.synthesis_item_count == 3
    assert entity.synthesis_confidence == "high"
    assert entity.synthesis_generated_at is not None


def test_synthesize_skips_entities_below_min_item_count(db, monkeypatch):
    user = _user(db, email="skip@x.com")
    entity = _entity(db, user.id, item_count=1)

    fake = _FakeChat({"summary": "should not be called", "confidence": "high"})
    monkeypatch.setattr(synth, "get_chat_provider", lambda: fake)

    result = synth.synthesize_entity(entity.id, db)
    assert result is None
    assert fake.calls == 0


def test_synthesize_no_contexts_returns_none(db, monkeypatch):
    """Entity with item_count but zero attached mentions → no evidence."""
    user = _user(db, email="noev@x.com")
    entity = _entity(db, user.id, item_count=5)
    # Deliberately DO NOT create ItemEntity rows

    fake = _FakeChat({"summary": "nope", "confidence": "low"})
    monkeypatch.setattr(synth, "get_chat_provider", lambda: fake)

    assert synth.synthesize_entity(entity.id, db) is None


def test_synthesize_noop_provider_graceful(db):
    """With the real NoOpChatProvider, synthesis returns None without crashing."""
    user = _user(db, email="noop@x.com")
    items = [_item(db, user.id, f"x-{i}") for i in range(3)]
    entity = _entity(db, user.id, name="NoOpEnt")
    _link_items(db, entity.id, [i.id for i in items])

    # Do NOT patch chat provider — default NoOpChatProvider returns {} which
    # fails validation.
    assert synth.synthesize_entity(entity.id, db) is None


def test_synthesize_invalid_json_rejected(db, monkeypatch):
    user = _user(db, email="bad@x.com")
    items = [_item(db, user.id, f"y-{i}") for i in range(3)]
    entity = _entity(db, user.id, name="BadJson")
    _link_items(db, entity.id, [i.id for i in items])

    # Missing required 'summary'
    fake = _FakeChat({"themes": ["x"], "confidence": "low"})
    monkeypatch.setattr(synth, "get_chat_provider", lambda: fake)

    assert synth.synthesize_entity(entity.id, db) is None


# ─── should_regenerate ────────────────────────────────────────────────────


def test_should_regenerate_first_time(db):
    user = _user(db, email="reg1@x.com")
    entity = _entity(db, user.id, item_count=3)
    assert synth.should_regenerate(entity)


def test_should_regenerate_below_min(db):
    user = _user(db, email="reg2@x.com")
    entity = _entity(db, user.id, item_count=1)
    assert synth.should_regenerate(entity) is False


def test_should_regenerate_respects_threshold(db):
    user = _user(db, email="reg3@x.com")
    entity = _entity(db, user.id, item_count=4)
    # Pretend we synthesised at 3 items, then gained 1 new → below default threshold of 3
    entity.synthesis_item_count = 3
    entity.synthesis_generated_at = datetime.now(timezone.utc) - timedelta(days=10)
    entity.synthesis = {"summary": "existing"}
    db.add(entity)
    db.commit()
    assert synth.should_regenerate(entity) is False


def test_should_regenerate_respects_interval(db):
    user = _user(db, email="reg4@x.com")
    entity = _entity(db, user.id, item_count=10)
    entity.synthesis_item_count = 3  # big delta = threshold met
    entity.synthesis_generated_at = datetime.now(timezone.utc) - timedelta(hours=1)
    entity.synthesis = {"summary": "existing"}
    db.add(entity)
    db.commit()
    assert synth.should_regenerate(entity) is False


def test_should_regenerate_threshold_and_interval_met(db):
    user = _user(db, email="reg5@x.com")
    entity = _entity(db, user.id, item_count=10)
    entity.synthesis_item_count = 3
    entity.synthesis_generated_at = datetime.now(timezone.utc) - timedelta(days=3)
    entity.synthesis = {"summary": "existing"}
    db.add(entity)
    db.commit()
    assert synth.should_regenerate(entity) is True


# ─── API endpoint ────────────────────────────────────────────────────────


def test_force_regenerate_endpoint(client, auth_headers, db, monkeypatch):
    from sqlmodel import select

    from fourdpocket.models.user import User as UserModel

    user = db.exec(
        select(UserModel).where(UserModel.email == "test@example.com")
    ).first()
    assert user is not None, "auth_headers should have registered test@example.com"

    items = [_item(db, user.id, f"forced-{i}") for i in range(3)]
    entity = _entity(db, user.id, name="ForceEnt")
    _link_items(db, entity.id, [i.id for i in items])

    fake = _FakeChat(
        {
            "summary": "Forced.",
            "themes": ["t"],
            "key_contexts": [],
            "relationships": [],
            "confidence": "medium",
        }
    )
    monkeypatch.setattr(synth, "get_chat_provider", lambda: fake)

    res = client.post(
        f"/api/v1/entities/{entity.id}/synthesize", headers=auth_headers
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "regenerated"
    assert data["synthesis"]["summary"] == "Forced."


def test_force_regenerate_returns_429_when_fresh(client, auth_headers, db, monkeypatch):
    from sqlmodel import select

    from fourdpocket.models.user import User as UserModel

    user = db.exec(
        select(UserModel).where(UserModel.email == "test@example.com")
    ).first()
    items = [_item(db, user.id, f"fresh-{i}") for i in range(3)]
    entity = _entity(db, user.id, name="FreshEnt")
    entity.synthesis = {"summary": "already"}
    entity.synthesis_item_count = 3
    entity.synthesis_generated_at = datetime.now(timezone.utc)
    db.add(entity)
    db.commit()
    _link_items(db, entity.id, [i.id for i in items])

    res = client.post(
        f"/api/v1/entities/{entity.id}/synthesize", headers=auth_headers
    )
    assert res.status_code == 429

    # With force=true it bypasses the cooldown
    fake = _FakeChat(
        {
            "summary": "Forced again.",
            "themes": [],
            "key_contexts": [],
            "relationships": [],
            "confidence": "low",
        }
    )
    monkeypatch.setattr(synth, "get_chat_provider", lambda: fake)
    res2 = client.post(
        f"/api/v1/entities/{entity.id}/synthesize?force=true", headers=auth_headers
    )
    assert res2.status_code == 200
