"""Share manager tests — create_share, add_recipient, revoke_share, validate_public_token."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, select

from fourdpocket.models.collection import Collection
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share, ShareRecipient, ShareRecipientRole, ShareType
from fourdpocket.models.tag import Tag
from fourdpocket.models.user import User
from fourdpocket.sharing.share_manager import (
    add_recipient,
    create_share,
    revoke_share,
    validate_public_token,
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


def _make_collection(db: Session, user_id: uuid.UUID, name: str = "Test Collection") -> Collection:
    coll = Collection(user_id=user_id, name=name)
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return coll


def _make_tag(db: Session, user_id: uuid.UUID, name: str = "test-tag") -> Tag:
    slug = name.lower().replace("_", "-")
    tag = Tag(user_id=user_id, name=name, slug=slug)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


# ---------------------------------------------------------------------------
# create_share tests
# ---------------------------------------------------------------------------

def test_create_item_share_associates_item_and_owner(db):
    alice = _make_user(db, "alice@test.com", "alice")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id)

    assert share.owner_id == alice.id
    assert share.item_id == item.id
    assert share.share_type == ShareType.item
    assert share.public is False


def test_create_collection_share_associates_collection_and_owner(db):
    alice = _make_user(db, "alice@test.com", "alice")
    coll = _make_collection(db, alice.id)

    share = create_share(db, alice.id, ShareType.collection, collection_id=coll.id)

    assert share.owner_id == alice.id
    assert share.collection_id == coll.id


def test_create_tag_share_associates_tag_and_owner(db):
    alice = _make_user(db, "alice@test.com", "alice")
    tag = _make_tag(db, alice.id)

    share = create_share(db, alice.id, ShareType.tag, tag_id=tag.id)

    assert share.owner_id == alice.id
    assert share.tag_id == tag.id


def test_create_share_with_expiration(db):
    alice = _make_user(db, "alice@test.com", "alice")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id, expires_hours=24)

    assert share.expires_at is not None
    # SQLite strips timezone info from stored datetimes, so compare naively
    assert share.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)


def test_create_share_with_public_token(db):
    alice = _make_user(db, "alice@test.com", "alice")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id, public=True)

    assert share.public is True
    assert share.public_token is not None
    assert len(share.public_token) > 20


def test_create_share_raises_for_non_owned_item(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, bob.id)  # Bob owns it

    with pytest.raises(ValueError, match="not owned"):
        create_share(db, alice.id, ShareType.item, item_id=item.id)


def test_create_share_raises_for_nonexistent_item(db):
    alice = _make_user(db, "alice@test.com", "alice")

    with pytest.raises(ValueError, match="not found"):
        create_share(db, alice.id, ShareType.item, item_id=uuid.uuid4())


# ---------------------------------------------------------------------------
# add_recipient tests
# ---------------------------------------------------------------------------

def test_add_recipient_creates_share_recipient(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id)
    recipient = add_recipient(db, share.id, bob.id, ShareRecipientRole.viewer)

    assert recipient.share_id == share.id
    assert recipient.user_id == bob.id
    assert recipient.role == ShareRecipientRole.viewer
    assert recipient.accepted is False


def test_add_recipient_does_not_duplicate(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id)
    first = add_recipient(db, share.id, bob.id)
    second = add_recipient(db, share.id, bob.id)

    assert first.id == second.id

    # Only one recipient in DB
    recipients = db.exec(select(ShareRecipient).where(ShareRecipient.share_id == share.id)).all()
    assert len(recipients) == 1


def test_add_recipient_with_editor_role(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id)
    recipient = add_recipient(db, share.id, bob.id, ShareRecipientRole.editor)

    assert recipient.role == ShareRecipientRole.editor


# ---------------------------------------------------------------------------
# revoke_share tests
# ---------------------------------------------------------------------------

def test_revoke_share_removes_share_and_recipients(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id)
    add_recipient(db, share.id, bob.id)

    result = revoke_share(db, share.id, alice.id)

    assert result is True
    assert db.get(Share, share.id) is None


def test_revoke_share_returns_false_for_non_owner(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    carol = _make_user(db, "carol@test.com", "carol")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id)

    # Bob tries to revoke Alice's share
    result = revoke_share(db, share.id, bob.id)

    assert result is False
    assert db.get(Share, share.id) is not None


def test_revoke_share_returns_false_for_nonexistent_share(db):
    alice = _make_user(db, "alice@test.com", "alice")

    result = revoke_share(db, uuid.uuid4(), alice.id)

    assert result is False


# ---------------------------------------------------------------------------
# validate_public_token tests
# ---------------------------------------------------------------------------

def test_validate_public_token_returns_share(db):
    alice = _make_user(db, "alice@test.com", "alice")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id, public=True)

    result = validate_public_token(db, share.public_token)

    assert result is not None
    assert result.id == share.id


def test_validate_public_token_returns_none_for_invalid_token(db):
    result = validate_public_token(db, "not-a-valid-token")

    assert result is None


def test_validate_public_token_returns_none_for_non_public_share(db):
    alice = _make_user(db, "alice@test.com", "alice")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id, public=False)

    result = validate_public_token(db, share.public_token)

    assert result is None


def test_validate_public_token_returns_none_for_expired_share(db, monkeypatch):
    """Expired shares return None from validate_public_token."""
    import fourdpocket.sharing.share_manager as sm_module

    alice = _make_user(db, "alice@test.com", "alice")
    item = _make_item(db, alice.id)

    share = create_share(db, alice.id, ShareType.item, item_id=item.id, public=True)

    # expires_at is set to 1 hour ago (in the past)
    share.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

    # Patch datetime so it appears to be "now" = 2030 (way after expiry)
    class _AwareFutureDatetime:
        @staticmethod
        def now(tz=None):
            if tz is None:
                return datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
            return datetime(2030, 1, 1, 12, 0, 0, tzinfo=tz)

    original = sm_module.datetime
    sm_module.datetime = _AwareFutureDatetime  # type: ignore
    try:
        result = validate_public_token(db, share.public_token)
    finally:
        sm_module.datetime = original  # type: ignore

    assert result is None
