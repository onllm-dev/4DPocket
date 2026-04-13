"""Sharing permission checks — critical for multi-user data isolation."""

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share, ShareRecipient, ShareRecipientRole, ShareType
from fourdpocket.models.tag import ItemTag, Tag
from fourdpocket.models.user import User
from fourdpocket.sharing.permissions import (
    can_edit_item,
    can_view_collection,
    can_view_item,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(db: Session, email: str, username: str) -> User:
    user = User(
        email=email,
        username=username,
        password_hash="x",
        display_name=email.split("@")[0],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_item(db: Session, user_id: uuid.UUID, title: str = "Test Item") -> KnowledgeItem:
    item = KnowledgeItem(
        user_id=user_id,
        title=title,
        content="Test content",
        item_type="note",
        source_platform="generic",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _make_tag(db: Session, user_id: uuid.UUID, name: str = "test-tag") -> Tag:
    slug = name.lower().replace("_", "-")
    tag = Tag(user_id=user_id, name=name, slug=slug)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def _make_collection(db: Session, user_id: uuid.UUID, name: str = "Test Collection") -> Collection:
    coll = Collection(user_id=user_id, name=name)
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return coll


def _add_item_to_collection(db: Session, collection_id: uuid.UUID, item_id: uuid.UUID) -> None:
    ci = CollectionItem(collection_id=collection_id, item_id=item_id)
    db.add(ci)
    db.commit()


def _make_share(
    db: Session,
    owner_id: uuid.UUID,
    share_type: ShareType,
    recipient_id: uuid.UUID,
    item_id: uuid.UUID | None = None,
    collection_id: uuid.UUID | None = None,
    tag_id: uuid.UUID | None = None,
    role: ShareRecipientRole = ShareRecipientRole.viewer,
    expires_hours: int | None = None,
    accepted: bool = True,
) -> Share:
    share = Share(
        owner_id=owner_id,
        share_type=share_type,
        item_id=item_id,
        collection_id=collection_id,
        tag_id=tag_id,
        public=False,
    )
    if expires_hours:
        share.expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    db.add(share)
    db.commit()
    db.refresh(share)

    recipient = ShareRecipient(
        share_id=share.id,
        user_id=recipient_id,
        role=role,
        accepted=accepted,
    )
    db.add(recipient)
    db.commit()
    return share


# ---------------------------------------------------------------------------
# can_view_item tests
# ---------------------------------------------------------------------------

def test_owner_can_view_own_item(db):
    alice = _make_user(db, "alice@test.com", "alice")
    item = _make_item(db, alice.id, "Alice's Item")

    assert can_view_item(db, alice.id, item.id) is True


def test_other_user_cannot_view_item_without_share(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Alice's Private Item")

    assert can_view_item(db, bob.id, item.id) is False


def test_direct_item_share_grants_view_access(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Alice's Shared Item")

    _make_share(db, alice.id, ShareType.item, bob.id, item_id=item.id)

    assert can_view_item(db, bob.id, item.id) is True


def test_direct_item_share_editor_grants_edit_access(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Alice's Editable Item")

    _make_share(db, alice.id, ShareType.item, bob.id, item_id=item.id, role=ShareRecipientRole.editor)

    assert can_edit_item(db, bob.id, item.id) is True


def test_direct_item_share_viewer_cannot_edit(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Alice's View-Only Item")

    _make_share(db, alice.id, ShareType.item, bob.id, item_id=item.id, role=ShareRecipientRole.viewer)

    assert can_edit_item(db, bob.id, item.id) is False


def test_tag_share_grants_access(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Item with Tag")
    tag = _make_tag(db, alice.id, "shared-tag")

    # Tag the item
    item_tag = ItemTag(item_id=item.id, tag_id=tag.id)
    db.add(item_tag)
    db.commit()

    # Share the tag
    _make_share(db, alice.id, ShareType.tag, bob.id, tag_id=tag.id)

    assert can_view_item(db, bob.id, item.id) is True


def test_collection_share_grants_access(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Item in Collection")
    coll = _make_collection(db, alice.id, "Alice's Collection")

    _add_item_to_collection(db, coll.id, item.id)
    _make_share(db, alice.id, ShareType.collection, bob.id, collection_id=coll.id)

    assert can_view_item(db, bob.id, item.id) is True


def test_revoked_share_denies_access(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Was Shared Item")

    share = _make_share(db, alice.id, ShareType.item, bob.id, item_id=item.id)

    # Revoke: delete the share
    recipients = db.exec(
        select(ShareRecipient).where(ShareRecipient.share_id == share.id)
    ).all()
    for r in recipients:
        db.delete(r)
    db.delete(share)
    db.commit()

    assert can_view_item(db, bob.id, item.id) is False


def test_expired_share_denies_access(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Expired Share Item")

    _make_share(db, alice.id, ShareType.item, bob.id, item_id=item.id, expires_hours=-1)

    assert can_view_item(db, bob.id, item.id) is False


def test_unaccepted_share_denies_access(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Unaccepted Share Item")

    _make_share(db, alice.id, ShareType.item, bob.id, item_id=item.id, accepted=False)

    assert can_view_item(db, bob.id, item.id) is False


def test_nonexistent_item_returns_false(db):
    alice = _make_user(db, "alice@test.com", "alice")
    fake_id = uuid.uuid4()

    assert can_view_item(db, alice.id, fake_id) is False


def test_cross_user_isolation_user_a_items_invisible_to_user_b(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")

    # Alice's items
    alice_item1 = _make_item(db, alice.id, "Alice Item 1")
    alice_item2 = _make_item(db, alice.id, "Alice Item 2")

    # Bob's items
    bob_item = _make_item(db, bob.id, "Bob's Item")

    # Bob has his own item
    assert can_view_item(db, bob.id, bob_item.id) is True

    # Bob cannot see Alice's items
    assert can_view_item(db, bob.id, alice_item1.id) is False
    assert can_view_item(db, bob.id, alice_item2.id) is False

    # Alice cannot see Bob's item
    assert can_view_item(db, alice.id, bob_item.id) is False


# ---------------------------------------------------------------------------
# can_view_collection tests
# ---------------------------------------------------------------------------

def test_owner_can_view_own_collection(db):
    alice = _make_user(db, "alice@test.com", "alice")
    coll = _make_collection(db, alice.id, "Alice's Collection")

    assert can_view_collection(db, alice.id, coll.id) is True


def test_other_user_cannot_view_collection_without_share(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    coll = _make_collection(db, alice.id, "Alice's Private Collection")

    assert can_view_collection(db, bob.id, coll.id) is False


def test_shared_collection_grants_view_access(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    coll = _make_collection(db, alice.id, "Alice's Shared Collection")

    _make_share(db, alice.id, ShareType.collection, bob.id, collection_id=coll.id)

    assert can_view_collection(db, bob.id, coll.id) is True


def test_nonexistent_collection_returns_false(db):
    alice = _make_user(db, "alice@test.com", "alice")
    fake_id = uuid.uuid4()

    assert can_view_collection(db, alice.id, fake_id) is False
