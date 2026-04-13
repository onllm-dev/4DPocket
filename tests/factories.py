"""Reusable test factories for creating domain objects."""

from sqlmodel import Session

from fourdpocket.models.api_token import ApiToken
from fourdpocket.models.collection import Collection
from fourdpocket.models.enrichment import EnrichmentStage
from fourdpocket.models.entity import Entity
from fourdpocket.models.item import KnowledgeItem as Item
from fourdpocket.models.item_chunk import ItemChunk
from fourdpocket.models.tag import Tag
from fourdpocket.models.user import User


def make_user(db: Session, email="factory@test.com", username="factoryuser", **kw) -> User:
    """Create a user with hashed password."""
    from fourdpocket.api.auth import hash_password

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password("TestPass123!"),
        display_name=kw.get("display_name", "Factory User"),
        is_admin=kw.get("is_admin", False),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_item(db: Session, user_id: int, url="https://example.com", **kw) -> Item:
    """Create an item with sensible defaults."""
    item = Item(
        user_id=user_id,
        url=url,
        title=kw.pop("title", "Test Item"),
        content=kw.pop("content", "Test content for testing."),
        item_type=kw.pop("item_type", "article"),
        source_platform=kw.pop("source_platform", "generic"),
        item_metadata=kw.pop("item_metadata", {}),
        **kw,  # Pass through reading_status, reading_progress, is_favorite, etc.
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def make_collection(db: Session, user_id: int, name="Test Collection", **kw) -> Collection:
    coll = Collection(user_id=user_id, name=name, **kw)
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return coll


def make_chunk(db: Session, item_id: int, user_id: int, content="chunk text", **kw) -> ItemChunk:
    chunk = ItemChunk(
        item_id=item_id,
        user_id=user_id,
        chunk_text=content,
        chunk_index=kw.get("chunk_index", 0),
        kind=kw.get("kind", "body"),
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk


def make_enrichment_stage(db: Session, item_id: int, stage: str, status="completed", **kw):
    es = EnrichmentStage(item_id=item_id, stage=stage, status=status, **kw)
    db.add(es)
    db.commit()
    db.refresh(es)
    return es


def make_entity(db: Session, user_id: int, name="Test Entity", entity_type="person", **kw):
    entity = Entity(user_id=user_id, name=name, entity_type=entity_type, **kw)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


def make_tag(db: Session, user_id: int, name="test-tag", **kw):
    slug = name.lower().replace(" ", "-").replace("_", "-")
    tag = Tag(user_id=user_id, name=name, slug=slug, **kw)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def make_pat(db: Session, user_id: int, **kw) -> tuple[ApiToken, str]:
    """Create a PAT and return (token_model, raw_token_string)."""
    import hashlib
    import secrets

    prefix = secrets.token_hex(3)
    raw_secret = secrets.token_urlsafe(32)
    raw_token = f"fdp_pat_{prefix}_{raw_secret}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token = ApiToken(
        user_id=user_id,
        name=kw.get("name", "test-token"),
        token_prefix=prefix,
        token_hash=token_hash,
        role=kw.get("role", "editor"),
        all_collections=kw.get("all_collections", True),
        allow_deletion=kw.get("allow_deletion", False),
        admin_scope=kw.get("admin_scope", False),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, raw_token
