"""Tests for ai/hierarchy.py."""

import uuid

from sqlmodel import Session, select

from fourdpocket.ai import hierarchy
from fourdpocket.models.tag import Tag
from fourdpocket.models.user import User


def _user(db: Session, email: str = "hier@test.com") -> User:
    u = User(email=email, username=email.split("@")[0], password_hash="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _tag(db: Session, user_id: uuid.UUID, name: str, slug: str) -> Tag:
    t = Tag(user_id=user_id, name=name, slug=slug, ai_generated=True)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


# ─── apply_hierarchy ──────────────────────────────────────────────────────────


def test_apply_hierarchy_creates_parent_tag(db):
    """When parent does not exist, it is created by recursive call."""
    user = _user(db)

    # Pre-create the child tag; apply_hierarchy will then create 'programming'
    # and recursively call itself to create 'technology' parent
    _tag(db, user.id, "Python", "python")

    hierarchy.apply_hierarchy("python", user.id, db)

    parent = db.exec(select(Tag).where(Tag.slug == "programming")).first()
    assert parent is not None
    assert parent.name == "programming"


def test_apply_hierarchy_skips_if_child_not_found(db):
    """Non-existent tag → no-op (function only operates on existing tags)."""
    user = _user(db)

    # apply_hierarchy on a non-existent tag should be a no-op
    hierarchy.apply_hierarchy("nonexistent-tag-xyz", user.id, db)

    # No tags should be created
    count = db.exec(select(Tag)).all()
    assert len(count) == 0


def test_apply_hierarchy_links_child_to_parent(db):
    """apply_hierarchy sets child.parent_id to the parent tag."""
    user = _user(db)

    # Pre-create child tag
    python_tag = _tag(db, user.id, "Python", "python")

    hierarchy.apply_hierarchy("python", user.id, db)

    db.refresh(python_tag)
    assert python_tag.parent_id is not None
    parent = db.get(Tag, python_tag.parent_id)
    assert parent.slug == "programming"


def test_apply_hierarchy_skips_if_already_has_parent(db):
    """Tag that already has a parent_id is not re-parented."""
    user = _user(db)

    # Pre-create python with existing parent
    parent_tag = _tag(db, user.id, "programming", "programming")
    child_tag = Tag(
        user_id=user.id, name="Python", slug="python",
        ai_generated=True, parent_id=parent_tag.id
    )
    db.add(child_tag)
    db.commit()
    db.refresh(child_tag)

    original_parent_id = child_tag.parent_id

    hierarchy.apply_hierarchy("python", user.id, db)

    db.refresh(child_tag)
    assert child_tag.parent_id == original_parent_id


def test_apply_hierarchy_reuses_existing_parent(db):
    """If parent tag already exists, it is reused."""
    user = _user(db)

    # Pre-create parent
    _tag(db, user.id, "programming", "programming")

    # Pre-create child
    python_tag = _tag(db, user.id, "Python", "python")

    hierarchy.apply_hierarchy("python", user.id, db)

    db.refresh(python_tag)
    # Parent should be the pre-created one
    parent = db.get(Tag, python_tag.parent_id)
    assert parent.slug == "programming"


def test_apply_hierarchy_recursive(db):
    """apply_hierarchy recursively applies to the parent."""
    user = _user(db)

    # Pre-create the python tag; apply_hierarchy will create parent chain:
    # python → programming → technology
    python_tag = _tag(db, user.id, "Python", "python")

    hierarchy.apply_hierarchy("python", user.id, db)

    db.refresh(python_tag)
    # Check the chain: python.parent should be programming
    prog_tag = db.get(Tag, python_tag.parent_id)
    assert prog_tag.slug == "programming"

    # programming.parent should be technology
    assert prog_tag.parent_id is not None
    tech_tag = db.get(Tag, prog_tag.parent_id)
    assert tech_tag.slug == "technology"


def test_apply_hierarchy_no_mapping_returns_early(db):
    """Tag with no HIERARCHY_MAP entry → no-op."""
    user = _user(db)

    # Pre-create the tag
    orphan_tag = _tag(db, user.id, "My Weird Tag", "my-weird-tag")

    hierarchy.apply_hierarchy("my-weird-tag", user.id, db)

    db.refresh(orphan_tag)
    assert orphan_tag.parent_id is None


# ─── HIERARCHY_MAP coverage ────────────────────────────────────────────────────


def test_hierarchy_map_has_expected_entries():
    """Verify key entries exist in HIERARCHY_MAP."""
    hmap = hierarchy.HIERARCHY_MAP
    assert hmap.get("python") == "programming"
    assert hmap.get("react") == "frontend"
    assert hmap.get("fastapi") == "backend"
    assert hmap.get("kubernetes") == "devops"
    assert hmap.get("machine-learning") == "ai"
    assert hmap.get("sql") == "data"
    assert hmap.get("tutorial") == "content-type"
    assert hmap.get("cooking") == "lifestyle"


def test_hierarchy_map_meta_chain():
    """Verify meta-category chains resolve correctly."""
    hmap = hierarchy.HIERARCHY_MAP
    assert hmap.get("frontend") == "programming"
    assert hmap.get("programming") == "technology"
    assert hmap.get("ai") == "technology"
