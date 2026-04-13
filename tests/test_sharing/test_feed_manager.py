"""Feed manager tests — subscribe, unsubscribe, get_feed_items."""

import uuid

from sqlmodel import Session, select

from fourdpocket.models.feed import KnowledgeFeed
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.share import Share, ShareRecipient, ShareRecipientRole, ShareType
from fourdpocket.models.user import User
from fourdpocket.sharing.feed_manager import (
    get_feed_items,
    subscribe,
    unsubscribe,
)
from fourdpocket.sharing.share_manager import create_share

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


# ---------------------------------------------------------------------------
# subscribe tests
# ---------------------------------------------------------------------------

def test_subscribe_creates_feed(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")

    feed = subscribe(db, bob.id, alice.id)

    assert feed.subscriber_id == bob.id
    assert feed.publisher_id == alice.id


def test_subscribe_idempotent(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")

    first = subscribe(db, bob.id, alice.id)
    second = subscribe(db, bob.id, alice.id)

    assert first.id == second.id


# ---------------------------------------------------------------------------
# unsubscribe tests
# ---------------------------------------------------------------------------

def test_unsubscribe_removes_feed(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")

    subscribe(db, bob.id, alice.id)
    result = unsubscribe(db, bob.id, alice.id)

    assert result is True
    feeds = db.exec(
        select(KnowledgeFeed).where(
            KnowledgeFeed.subscriber_id == bob.id,
            KnowledgeFeed.publisher_id == alice.id,
        )
    ).all()
    assert len(feeds) == 0


def test_unsubscribe_returns_false_when_not_subscribed(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")

    result = unsubscribe(db, bob.id, alice.id)

    assert result is False


# ---------------------------------------------------------------------------
# get_feed_items tests
# ---------------------------------------------------------------------------

def test_get_feed_items_returns_publisher_items(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Alice's Post")

    subscribe(db, bob.id, alice.id)

    # Make the item publicly shared so it appears in the feed
    create_share(db, alice.id, ShareType.item, item_id=item.id, public=True)

    items = get_feed_items(db, bob.id, limit=10)

    assert len(items) == 1
    assert items[0].title == "Alice's Post"


def test_get_feed_items_respects_offset(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item1 = _make_item(db, alice.id, "First")
    item2 = _make_item(db, alice.id, "Second")

    subscribe(db, bob.id, alice.id)

    # Make items publicly shared so they appear in the feed
    create_share(db, alice.id, ShareType.item, item_id=item1.id, public=True)
    create_share(db, alice.id, ShareType.item, item_id=item2.id, public=True)

    page1 = get_feed_items(db, bob.id, limit=1, offset=0)
    page2 = get_feed_items(db, bob.id, limit=1, offset=1)

    assert len(page1) == 1
    assert len(page2) == 1
    assert page1[0].title != page2[0].title


def test_get_feed_items_excludes_archived_items(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Archived Post")
    item.is_archived = True
    db.add(item)
    db.commit()

    subscribe(db, bob.id, alice.id)

    items = get_feed_items(db, bob.id)

    assert len(items) == 0


def test_get_feed_items_returns_empty_when_not_following_anyone(db):
    alice = _make_user(db, "alice@test.com", "alice")

    items = get_feed_items(db, alice.id)

    assert items == []


def test_get_feed_items_excludes_non_shared_private_items(db):
    """Items with no public share and no recipient are not accessible in feed."""
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    carol = _make_user(db, "carol@test.com", "carol")

    # Alice has a private item (no shares at all)
    _make_item(db, alice.id, "Alice Private")

    # Bob follows Alice but Alice hasn't shared anything
    subscribe(db, bob.id, alice.id)

    items = get_feed_items(db, bob.id)

    assert items == []


def test_get_feed_items_includes_items_shared_with_subscriber(db):
    alice = _make_user(db, "alice@test.com", "alice")
    bob = _make_user(db, "bob@test.com", "bob")
    item = _make_item(db, alice.id, "Shared with Bob")

    # Alice shares item directly with Bob
    share = Share(
        owner_id=alice.id,
        share_type=ShareType.item,
        item_id=item.id,
        public=False,
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    recipient = ShareRecipient(
        share_id=share.id,
        user_id=bob.id,
        role=ShareRecipientRole.viewer,
        accepted=True,
    )
    db.add(recipient)
    db.commit()

    subscribe(db, bob.id, alice.id)

    items = get_feed_items(db, bob.id)

    assert len(items) == 1
    assert items[0].title == "Shared with Bob"
