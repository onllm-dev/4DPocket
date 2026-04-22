"""Tests for RSS feed API endpoints."""

import socket
import uuid


class TestListFeeds:
    """List RSS feeds endpoint tests."""

    def test_list_feeds_empty(self, client, auth_headers):
        """No feeds registered returns empty list."""
        resp = client.get("/api/v1/rss", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_feeds_returns_users_feeds(self, client, auth_headers):
        """List feeds returns only the current user's feeds."""
        client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/feed1.xml", "title": "Feed 1"},
            headers=auth_headers,
        )
        client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/feed2.xml", "title": "Feed 2"},
            headers=auth_headers,
        )

        resp = client.get("/api/v1/rss", headers=auth_headers)
        assert resp.status_code == 200
        feeds = resp.json()
        assert len(feeds) == 2
        titles = {f["title"] for f in feeds}
        assert "Feed 1" in titles
        assert "Feed 2" in titles

    def test_list_feeds_requires_auth(self, client):
        """Without auth returns 401."""
        resp = client.get("/api/v1/rss")
        assert resp.status_code == 401


class TestCreateFeed:
    """Create RSS feed endpoint tests."""

    def test_create_feed_success(self, client, auth_headers):
        """Creating a feed with a safe URL succeeds."""
        resp = client.post(
            "/api/v1/rss",
            json={
                "url": "https://example.com/feed.xml",
                "title": "My RSS Feed",
                "category": "tech",
                "poll_interval": 1800,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://example.com/feed.xml"
        assert data["title"] == "My RSS Feed"
        assert data["category"] == "tech"
        assert data["poll_interval"] == 1800
        assert "id" in data

    def test_create_feed_blocked_internal_url(self, client, auth_headers):
        """Feed URL pointing to internal/private network is rejected."""
        resp = client.post(
            "/api/v1/rss",
            json={"url": "http://127.0.0.1/feed.xml", "title": "Local Feed"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "blocked" in resp.json()["detail"].lower()

    def test_create_feed_blocked_localhost(self, client, auth_headers):
        """Feed URL with localhost hostname is rejected."""
        resp = client.post(
            "/api/v1/rss",
            json={"url": "http://localhost/feed.xml", "title": "Localhost Feed"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_feed_blocked_local_domain(self, client, auth_headers):
        """Feed URL with .local TLD is rejected."""
        resp = client.post(
            "/api/v1/rss",
            json={"url": "https://mycomputer.local/feed.xml", "title": "Local Feed"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_feed_blocked_hostname_resolving_to_loopback(
        self, client, auth_headers, monkeypatch
    ):
        """Hostnames resolving to loopback addresses are rejected."""

        def fake_getaddrinfo(*args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]

        monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

        resp = client.post(
            "/api/v1/rss",
            json={"url": "https://blocked.example/feed.xml", "title": "Blocked Feed"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_create_feed_requires_auth(self, client):
        """Without auth returns 401."""
        resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/feed.xml", "title": "No Auth"},
        )
        assert resp.status_code == 401


class TestUpdateFeed:
    """Update RSS feed endpoint tests."""

    def test_update_feed_title(self, client, auth_headers):
        """Owner can update feed title."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/update-test.xml", "title": "Original"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/rss/{feed_id}",
            json={"title": "Updated Title"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_update_feed_activate(self, client, auth_headers):
        """Owner can activate/deactivate a feed."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/activate-test.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/rss/{feed_id}",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_update_nonexistent_feed(self, client, auth_headers):
        """Updating a non-existent feed returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.patch(
            f"/api/v1/rss/{fake_id}",
            json={"title": "Does Not Exist"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_update_other_users_feed(self, client, auth_headers, second_user_headers):
        """User cannot update another user's feed."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/other-feed.xml", "title": "Not Yours"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/rss/{feed_id}",
            json={"title": "Hacked"},
            headers=second_user_headers,
        )
        assert resp.status_code == 404


class TestDeleteFeed:
    """Delete RSS feed endpoint tests."""

    def test_delete_feed_success(self, client, auth_headers):
        """Owner can delete their feed."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/delete-test.xml", "title": "To Delete"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/v1/rss/{feed_id}", headers=auth_headers)
        assert del_resp.status_code == 204

        # Verify feed is gone by listing — should not appear
        list_resp = client.get("/api/v1/rss", headers=auth_headers)
        assert list_resp.status_code == 200
        feed_ids = {f["id"] for f in list_resp.json()}
        assert feed_id not in feed_ids

    def test_delete_other_users_feed(self, client, auth_headers, second_user_headers):
        """User cannot delete another user's feed."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/protected-feed.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/rss/{feed_id}", headers=second_user_headers)
        assert resp.status_code == 404

    def test_delete_nonexistent_feed(self, client, auth_headers):
        """Deleting a non-existent feed returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.delete(f"/api/v1/rss/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404


class TestListFeedEntries:
    """List feed entries endpoint tests."""

    def test_list_feed_entries_empty(self, client, auth_headers):
        """Feed with no entries returns empty list."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/empty-feed.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/rss/{feed_id}/entries", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_feed_entries_other_users_feed(self, client, auth_headers, second_user_headers):
        """Cannot list entries of another user's feed."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/entries-feed.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/rss/{feed_id}/entries", headers=second_user_headers)
        assert resp.status_code == 404


class TestUpdateFeedEntryStatus:
    """Update feed entry status endpoint tests."""

    def test_update_entry_status_nonexistent_returns_404(self, client, auth_headers):
        """Non-existent entry returns 404."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/status-feed.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        fake_entry_id = str(uuid.uuid4())
        resp = client.patch(
            f"/api/v1/rss/{feed_id}/entries/{fake_entry_id}",
            json={"status": "approved"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestApproveFeedEntry:
    """Approve feed entry endpoint tests."""

    def test_approve_nonexistent_feed(self, client, auth_headers):
        """Approving entry in non-existent feed returns 404."""
        fake_feed_id = str(uuid.uuid4())
        fake_entry_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/rss/{fake_feed_id}/entries/{fake_entry_id}/approve",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_approve_entry_other_users_feed(self, client, auth_headers, second_user_headers):
        """Cannot approve entry in another user's feed."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/approve-feed.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]
        fake_entry_id = str(uuid.uuid4())

        resp = client.post(
            f"/api/v1/rss/{feed_id}/entries/{fake_entry_id}/approve",
            headers=second_user_headers,
        )
        assert resp.status_code == 404


class TestFetchFeedNow:
    """Manual feed fetch endpoint tests."""

    def test_fetch_feed_not_found(self, client, auth_headers):
        """Fetching a non-existent feed returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/rss/{fake_id}/fetch", headers=auth_headers)
        assert resp.status_code == 404

    def test_fetch_other_users_feed(self, client, auth_headers, second_user_headers):
        """Cannot manually fetch another user's feed."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/fetch-feed.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.post(f"/api/v1/rss/{feed_id}/fetch", headers=second_user_headers)
        assert resp.status_code == 404


class TestRSSFeedScoping:
    """RSS feed user scoping tests."""

    def test_user_cannot_see_other_users_feeds(
        self, client, auth_headers, second_user_headers
    ):
        """Feeds are scoped to the owning user."""
        # User A creates a feed
        client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/user-a-feed.xml", "title": "User A Feed"},
            headers=auth_headers,
        )

        # User B lists feeds
        resp = client.get("/api/v1/rss", headers=second_user_headers)
        assert resp.status_code == 200
        feeds = resp.json()
        titles = {f.get("title", "") for f in feeds}
        assert "User A Feed" not in titles

    def test_feed_id_is_uuid(self, client, auth_headers):
        """Created feed has a valid UUID id."""
        resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/uuid-test.xml", "title": "UUID Test"},
            headers=auth_headers,
        )
        feed_id = resp.json()["id"]
        # Should be parseable as UUID
        parsed = uuid.UUID(feed_id)
        assert str(parsed) == feed_id


# === PHASE 3 MOPUP ADDITIONS ===

class TestFeedApprovalQueue:
    """Feed entry approval queue endpoint tests."""

    def test_list_feed_entries_with_pending_filter(self, client, auth_headers, db):
        """List pending entries for an approval-mode feed."""
        from sqlmodel import select

        from fourdpocket.models.feed_entry import FeedEntry
        from fourdpocket.models.rss_feed import RSSFeed
        from fourdpocket.models.user import User

        user = db.exec(select(User)).first()
        feed = RSSFeed(
            user_id=user.id,
            url="https://example.com/approval-feed.xml",
            name="Approval Feed",
            mode="approval",
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)

        entry = FeedEntry(
            feed_id=feed.id,
            user_id=user.id,
            url="https://example.com/entry",
            title="Pending Entry",
            status="pending",
        )
        db.add(entry)
        db.commit()

        resp = client.get(f"/api/v1/rss/{feed.id}/entries?status_filter=pending", headers=auth_headers)
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) == 1
        assert entries[0]["status"] == "pending"
        assert entries[0]["title"] == "Pending Entry"

    def test_approve_entry_creates_knowledge_item(self, client, auth_headers, db):
        """Approving a pending entry creates a KnowledgeItem."""
        from sqlmodel import select

        from fourdpocket.models.feed_entry import FeedEntry
        from fourdpocket.models.item import KnowledgeItem
        from fourdpocket.models.rss_feed import RSSFeed
        from fourdpocket.models.user import User

        user = db.exec(select(User)).first()
        feed = RSSFeed(
            user_id=user.id,
            url="https://example.com/approve-feed.xml",
            name="Approve Feed",
            mode="approval",
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)

        entry = FeedEntry(
            feed_id=feed.id,
            user_id=user.id,
            url="https://example.com/approve-me",
            title="To Approve",
            content_snippet="Some content",
            status="pending",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        resp = client.post(
            f"/api/v1/rss/{feed.id}/entries/{entry.id}/approve",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"
        assert "item_id" in data

        # Verify KnowledgeItem was created
        item_id = uuid.UUID(data["item_id"])
        item = db.get(KnowledgeItem, item_id)
        assert item is not None
        assert item.url == "https://example.com/approve-me"
        assert item.title == "To Approve"

        # Verify entry status updated
        db.refresh(entry)
        assert entry.status == "approved"

    def test_reject_entry_sets_status_to_rejected(self, client, auth_headers, db):
        """Rejecting a pending entry marks it as rejected."""
        from sqlmodel import select

        from fourdpocket.models.feed_entry import FeedEntry
        from fourdpocket.models.rss_feed import RSSFeed
        from fourdpocket.models.user import User

        user = db.exec(select(User)).first()
        feed = RSSFeed(
            user_id=user.id,
            url="https://example.com/reject-feed.xml",
            name="Reject Feed",
            mode="approval",
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)

        entry = FeedEntry(
            feed_id=feed.id,
            user_id=user.id,
            url="https://example.com/reject-me",
            title="To Reject",
            status="pending",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        resp = client.patch(
            f"/api/v1/rss/{feed.id}/entries/{entry.id}",
            json={"status": "rejected"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

        # Verify entry is still present (not deleted)
        db.refresh(entry)
        assert entry.status == "rejected"

    def test_update_entry_invalid_status_returns_400(self, client, auth_headers, db):
        """Updating entry with invalid status returns 400."""
        from sqlmodel import select

        from fourdpocket.models.feed_entry import FeedEntry
        from fourdpocket.models.rss_feed import RSSFeed
        from fourdpocket.models.user import User

        user = db.exec(select(User)).first()
        feed = RSSFeed(
            user_id=user.id,
            url="https://example.com/invalid-status-feed.xml",
            name="Invalid Status Feed",
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)

        entry = FeedEntry(
            feed_id=feed.id,
            user_id=user.id,
            url="https://example.com/status-test",
            title="Status Test",
            status="pending",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        resp = client.patch(
            f"/api/v1/rss/{feed.id}/entries/{entry.id}",
            json={"status": "maybe"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "approved" in resp.json()["detail"] or "rejected" in resp.json()["detail"]


# === BUG REGRESSION TESTS ===

class TestCreateFeedCollectionOwnership:
    """Regression: create_feed must validate target_collection_id ownership.

    Bug: target_collection_id was saved without verifying it belongs to
    current_user. An attacker could pin a feed to another user's collection.
    Fixed in: src/fourdpocket/api/rss.py create_feed
    """

    def test_create_feed_with_unowned_collection_returns_404(
        self, client, auth_headers, second_user_headers
    ):
        """Cannot create a feed targeting another user's collection."""
        # Second user creates a collection
        coll_resp = client.post(
            "/api/v1/collections",
            json={"name": "Second User Collection"},
            headers=second_user_headers,
        )
        assert coll_resp.status_code == 201
        other_collection_id = coll_resp.json()["id"]

        # First user tries to use it as target
        resp = client.post(
            "/api/v1/rss",
            json={
                "url": "https://example.com/feed.xml",
                "title": "Hijack Feed",
                "target_collection_id": other_collection_id,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_create_feed_with_owned_collection_succeeds(self, client, auth_headers):
        """Creating a feed with own collection succeeds."""
        coll_resp = client.post(
            "/api/v1/collections",
            json={"name": "My Collection"},
            headers=auth_headers,
        )
        assert coll_resp.status_code == 201
        my_collection_id = coll_resp.json()["id"]

        resp = client.post(
            "/api/v1/rss",
            json={
                "url": "https://example.com/feed.xml",
                "title": "My Feed",
                "target_collection_id": my_collection_id,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["target_collection_id"] == my_collection_id


class TestUpdateFeedAllowlist:
    """Regression: update_feed must use an allowlist, not blanket setattr.

    Bug: any field from RSSFeedUpdate was applied via setattr with no
    restriction. target_collection_id required ownership validation too.
    Fixed in: src/fourdpocket/api/rss.py update_feed
    """

    def test_update_feed_target_collection_to_unowned_returns_404(
        self, client, auth_headers, second_user_headers
    ):
        """Updating target_collection_id to another user's collection returns 404."""
        # Second user creates a collection
        coll_resp = client.post(
            "/api/v1/collections",
            json={"name": "Second User Coll"},
            headers=second_user_headers,
        )
        other_collection_id = coll_resp.json()["id"]

        # First user creates a feed
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/update-coll.xml", "title": "Feed"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        # First user tries to set target to second user's collection
        resp = client.patch(
            f"/api/v1/rss/{feed_id}",
            json={"target_collection_id": other_collection_id},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_update_feed_target_collection_to_owned_succeeds(
        self, client, auth_headers
    ):
        """Updating target_collection_id to own collection succeeds."""
        coll_resp = client.post(
            "/api/v1/collections",
            json={"name": "My Coll"},
            headers=auth_headers,
        )
        my_collection_id = coll_resp.json()["id"]

        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/update-own-coll.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/rss/{feed_id}",
            json={"target_collection_id": my_collection_id},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["target_collection_id"] == my_collection_id


class TestApproveFeedEntryCollectionOwnership:
    """Regression: approve_feed_entry must re-verify collection ownership.

    Bug: CollectionItem was created using feed.target_collection_id without
    re-checking that the collection still exists and belongs to current_user.
    Fixed in: src/fourdpocket/api/rss.py approve_feed_entry
    """

    def test_approve_entry_with_deleted_collection_still_creates_item(
        self, client, auth_headers, db
    ):
        """If target collection was deleted, approve still creates the item (no crash)."""
        from sqlmodel import select

        from fourdpocket.models.collection import Collection
        from fourdpocket.models.feed_entry import FeedEntry
        from fourdpocket.models.rss_feed import RSSFeed
        from fourdpocket.models.user import User

        user = db.exec(select(User)).first()

        # Create a collection then delete it
        coll = Collection(user_id=user.id, name="Ephemeral")
        db.add(coll)
        db.commit()
        db.refresh(coll)
        coll_id = coll.id
        db.delete(coll)
        db.commit()

        feed = RSSFeed(
            user_id=user.id,
            url="https://example.com/ghost-coll.xml",
            mode="approval",
            target_collection_id=coll_id,
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)

        entry = FeedEntry(
            feed_id=feed.id,
            user_id=user.id,
            url="https://example.com/ghost-entry",
            title="Ghost Entry",
            status="pending",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        resp = client.post(
            f"/api/v1/rss/{feed.id}/entries/{entry.id}/approve",
            headers=auth_headers,
        )
        # Should succeed (item created) even though collection is gone — no FK crash
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"


class TestDoubleApproveRace:
    """Regression: approving an already-approved entry must return 400.

    Bug: approve_feed_entry had no guard against double-approval, allowing a
    race condition to create duplicate KnowledgeItems.
    Fixed in: src/fourdpocket/api/rss.py approve_feed_entry
    """

    def test_approve_already_approved_entry_returns_400(self, client, auth_headers, db):
        """Second approve of same entry returns 400, not a duplicate item."""
        from sqlmodel import select

        from fourdpocket.models.feed_entry import FeedEntry
        from fourdpocket.models.rss_feed import RSSFeed
        from fourdpocket.models.user import User

        user = db.exec(select(User)).first()
        feed = RSSFeed(
            user_id=user.id,
            url="https://example.com/double-approve.xml",
            mode="approval",
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)

        entry = FeedEntry(
            feed_id=feed.id,
            user_id=user.id,
            url="https://example.com/double-approve-entry",
            title="Double Approve",
            status="pending",
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        # First approval succeeds
        resp1 = client.post(
            f"/api/v1/rss/{feed.id}/entries/{entry.id}/approve",
            headers=auth_headers,
        )
        assert resp1.status_code == 200

        # Second approval must fail with 400
        resp2 = client.post(
            f"/api/v1/rss/{feed.id}/entries/{entry.id}/approve",
            headers=auth_headers,
        )
        assert resp2.status_code == 400
        assert "already approved" in resp2.json()["detail"].lower()


class TestPollIntervalMinimum:
    """Regression: poll_interval must be at least 300 seconds (5 minutes).

    Bug: RSSFeedCreate and RSSFeedUpdate accepted any integer poll_interval,
    allowing sub-300-second values that could hammer external servers.
    Fixed in: src/fourdpocket/api/rss.py RSSFeedCreate, RSSFeedUpdate
    """

    def test_create_feed_with_poll_interval_below_300_returns_422(self, client, auth_headers):
        """poll_interval < 300 is rejected at creation."""
        resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/fast-feed.xml", "poll_interval": 60},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_create_feed_with_poll_interval_300_is_accepted(self, client, auth_headers):
        """poll_interval == 300 is the minimum allowed."""
        resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/min-poll.xml", "poll_interval": 300},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["poll_interval"] == 300

    def test_update_feed_with_poll_interval_below_300_returns_422(self, client, auth_headers):
        """Updating poll_interval to < 300 is rejected."""
        create_resp = client.post(
            "/api/v1/rss",
            json={"url": "https://example.com/update-poll.xml"},
            headers=auth_headers,
        )
        feed_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/rss/{feed_id}",
            json={"poll_interval": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 422
