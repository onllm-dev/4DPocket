"""Serialization tests for all MCP response types."""

import uuid

from sqlmodel import Session

from fourdpocket.mcp import serializers as ser
from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.entity import Entity, EntityAlias, ItemEntity
from fourdpocket.models.entity_relation import EntityRelation
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.item_chunk import ItemChunk
from fourdpocket.models.tag import ItemTag, Tag


def _user(db: Session, email: str) -> uuid.UUID:
    from fourdpocket.models.user import User
    u = User(email=email, username=email.split("@")[0], password_hash="x", display_name="T")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u.id


def _item(db: Session, user_id: uuid.UUID, **kw) -> KnowledgeItem:
    it = KnowledgeItem(
        user_id=user_id,
        title=kw.get("title", "Test Item"),
        content=kw.get("content", "Test content"),
        url=kw.get("url", "https://example.com"),
        item_type=kw.get("item_type", "note"),
        source_platform=kw.get("source_platform", "generic"),
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return it


def _collection(db: Session, user_id: uuid.UUID, name: str = "Test Coll") -> Collection:
    c = Collection(user_id=user_id, name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _tag(db: Session, user_id: uuid.UUID, name: str) -> Tag:
    t = Tag(user_id=user_id, name=name, slug=name)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _entity(db: Session, user_id: uuid.UUID, name: str = "Test Entity") -> Entity:
    e = Entity(user_id=user_id, canonical_name=name, entity_type="person")
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _chunk(db: Session, item_id: uuid.UUID, user_id: uuid.UUID) -> ItemChunk:
    chunk = ItemChunk(
        item_id=item_id,
        user_id=user_id,
        chunk_order=0,
        text="seed text for chunk",
        token_count=4,
        char_start=0,
        char_end=18,
        content_hash="seed",
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


# ─── knowledge_brief ────────────────────────────────────────────────────────


def test_knowledge_brief_basic(db):
    user_id = _user(db, "kb@test.com")
    item = _item(db, user_id, title="Brief Item", content="Content here")

    result = ser.knowledge_brief(item)

    assert result["id"] == str(item.id)
    assert result["title"] == "Brief Item"
    assert result["url"] == "https://example.com"
    assert result["item_type"] == "note"
    assert result["source_platform"] == "generic"
    assert result["is_favorite"] is False
    assert result["is_archived"] is False
    assert "created_at" in result


def test_knowledge_brief_datetime_iso_format(db):
    from datetime import datetime, timezone

    user_id = _user(db, "kbdt@test.com")
    item = _item(db, user_id)
    item.created_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    db.add(item)
    db.commit()

    result = ser.knowledge_brief(item)

    assert result["created_at"].startswith("2024-01-15T12:00:00")


def test_knowledge_brief_optional_fields_null(db):
    user_id = _user(db, "kbn@test.com")
    item = _item(db, user_id, url=None)
    assert item.url is None

    result = ser.knowledge_brief(item)

    assert result["url"] is None


# ─── knowledge_detail ────────────────────────────────────────────────────────


def test_knowledge_detail_includes_brief_fields(db):
    user_id = _user(db, "kd@test.com")
    item = _item(db, user_id, title="Detail Item")

    result = ser.knowledge_detail(db, item)

    assert result["id"] == str(item.id)
    assert result["title"] == "Detail Item"
    assert "description" in result
    assert "content" in result
    assert "tags" in result
    assert "entities" in result
    assert "collections" in result
    assert "chunk_count" in result


def test_knowledge_detail_tags(db):
    user_id = _user(db, "kdt@test.com")
    item = _item(db, user_id)
    tag = _tag(db, user_id, "python")
    db.add(ItemTag(item_id=item.id, tag_id=tag.id))
    db.commit()

    result = ser.knowledge_detail(db, item)

    assert "python" in result["tags"]


def test_knowledge_detail_entities(db):
    user_id = _user(db, "kde@test.com")
    item = _item(db, user_id)
    entity = _entity(db, user_id, "Python")
    db.add(ItemEntity(item_id=item.id, entity_id=entity.id))
    db.commit()

    result = ser.knowledge_detail(db, item)

    assert len(result["entities"]) == 1
    assert result["entities"][0]["canonical_name"] == "Python"


def test_knowledge_detail_collections(db):
    user_id = _user(db, "kdc@test.com")
    item = _item(db, user_id)
    coll = _collection(db, user_id, "Work")
    db.add(CollectionItem(collection_id=coll.id, item_id=item.id))
    db.commit()

    result = ser.knowledge_detail(db, item)

    assert len(result["collections"]) == 1
    assert result["collections"][0]["name"] == "Work"


def test_knowledge_detail_chunk_count(db):
    user_id = _user(db, "kdcc@test.com")
    item = _item(db, user_id)
    _chunk(db, item.id, user_id)
    # Use different chunk_order to avoid unique constraint
    chunk2 = ItemChunk(
        item_id=item.id,
        user_id=user_id,
        chunk_order=1,
        text="second chunk text",
        token_count=3,
        char_start=0,
        char_end=17,
        content_hash="seed2",
    )
    db.add(chunk2)
    db.commit()

    result = ser.knowledge_detail(db, item)

    assert result["chunk_count"] == 2


# ─── collection_brief ──────────────────────────────────────────────────────


def test_collection_brief_basic(db):
    user_id = _user(db, "cb@test.com")
    coll = _collection(db, user_id, "My Collection")

    result = ser.collection_brief(db, coll)

    assert result["id"] == str(coll.id)
    assert result["name"] == "My Collection"
    assert result["description"] is None
    assert result["is_smart"] is False
    assert result["item_count"] == 0


def test_collection_brief_with_items(db):
    user_id = _user(db, "cbwi@test.com")
    coll = _collection(db, user_id)
    item = _item(db, user_id)
    db.add(CollectionItem(collection_id=coll.id, item_id=item.id))
    db.commit()

    result = ser.collection_brief(db, coll)

    assert result["item_count"] == 1


# ─── entity_brief ────────────────────────────────────────────────────────────


def test_entity_brief_basic(db):
    user_id = _user(db, "eb@test.com")
    entity = _entity(db, user_id, "Claude AI")

    result = ser.entity_brief(entity)

    assert result["id"] == str(entity.id)
    assert result["canonical_name"] == "Claude AI"
    assert result["entity_type"] == "person"
    assert result["item_count"] == 0


# ─── entity_with_synthesis ──────────────────────────────────────────────────


def test_entity_with_synthesis_dict(db):
    user_id = _user(db, "ews@test.com")
    entity = _entity(db, user_id, "Synth Entity")
    entity.synthesis = {"summary": "A helpful assistant", "themes": ["AI"]}
    entity.synthesis_generated_at = None
    entity.synthesis_confidence = "high"
    db.add(entity)
    db.commit()

    result = ser.entity_with_synthesis(db, entity)

    assert result["synthesis"]["summary"] == "A helpful assistant"
    assert result["aliases"] == []
    assert result["synthesis_confidence"] == "high"


def test_entity_with_synthesis_string(db):
    user_id = _user(db, "ewss@test.com")
    entity = _entity(db, user_id, "Str Synth Entity")
    entity.synthesis = "Simple synthesis text"
    entity.synthesis_generated_at = None
    db.add(entity)
    db.commit()

    result = ser.entity_with_synthesis(db, entity)

    # String synthesis is wrapped as {"summary": <string>}
    assert result["synthesis"]["summary"] == "Simple synthesis text"


def test_entity_with_synthesis_aliases(db):
    user_id = _user(db, "ewsa@test.com")
    entity = _entity(db, user_id, "Alias Entity")
    db.add(EntityAlias(entity_id=entity.id, alias="alias1"))
    db.add(EntityAlias(entity_id=entity.id, alias="alias2"))
    db.commit()

    result = ser.entity_with_synthesis(db, entity)

    assert set(result["aliases"]) == {"alias1", "alias2"}


# ─── related_entity ──────────────────────────────────────────────────────────


def test_related_entity_basic(db):

    user_id = _user(db, "re@test.com")
    entity = _entity(db, user_id, "Related Entity")
    relation = EntityRelation(
        user_id=user_id,
        source_id=entity.id,
        target_id=entity.id,
        keywords="test,related",
        description="A test relation",
        weight=0.85,
    )
    db.add(relation)
    db.commit()

    result = ser.related_entity(entity, relation)

    assert result["entity"]["canonical_name"] == "Related Entity"
    assert result["relation"]["keywords"] == "test,related"
    assert result["relation"]["weight"] == 0.85


# ─── resolve_entity_ref ────────────────────────────────────────────────────


def test_resolve_entity_ref_by_uuid(db):
    user_id = _user(db, "rebuuid@test.com")
    entity = _entity(db, user_id, "UUID Entity")

    result = ser.resolve_entity_ref(db, user_id, str(entity.id))

    assert result is not None
    assert result.id == entity.id


def test_resolve_entity_ref_by_name(db):
    user_id = _user(db, "rebname@test.com")
    _entity(db, user_id, "Named Entity")

    result = ser.resolve_entity_ref(db, user_id, "Named Entity")

    assert result is not None
    assert result.canonical_name == "Named Entity"


def test_resolve_entity_ref_by_alias(db):
    user_id = _user(db, "rebalias@test.com")
    entity = _entity(db, user_id, "Canonical Entity")
    db.add(EntityAlias(entity_id=entity.id, alias="My Alias"))
    db.commit()

    result = ser.resolve_entity_ref(db, user_id, "My Alias")

    assert result is not None
    assert result.canonical_name == "Canonical Entity"


def test_resolve_entity_ref_case_insensitive(db):
    user_id = _user(db, "rebcins@test.com")
    _entity(db, user_id, "CaseSensitive")

    result = ser.resolve_entity_ref(db, user_id, "casesensitive")

    assert result is not None


def test_resolve_entity_ref_not_found(db):
    user_id = _user(db, "rebnf@test.com")

    result = ser.resolve_entity_ref(db, user_id, "DoesNotExist")

    assert result is None


# ─── ISO helper ─────────────────────────────────────────────────────────────


def test_iso_none_returns_none():
    assert ser._iso(None) is None


def test_iso_datetime_returns_iso():
    from datetime import datetime, timezone

    dt = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    assert ser._iso(dt) == "2024-06-15T10:30:00+00:00"
