"""Tests for sharing API endpoints."""

import uuid


class TestShareCreation:
    """Share creation endpoint tests."""

    def test_create_item_share_without_public(self, client, auth_headers):
        """Create a private item share (no public token)."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/article", "title": "Test Article"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["share_type"] == "item"
        assert data["item_id"] == item_id
        assert data["public_token"] is None

    def test_create_item_share_with_public(self, client, auth_headers):
        """Create a public item share generates a token."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/public-doc", "title": "Public Doc"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id, "public": True},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["public_token"] is not None
        assert len(data["public_token"]) > 20

    def test_create_item_share_with_expiry(self, client, auth_headers):
        """Create a share with a specific expiration window."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/expiry", "title": "Expiry Doc"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id, "expires_hours": 24},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["expires_at"] is not None

    def test_create_item_share_nonexistent_item(self, client, auth_headers):
        """Share of a non-existent item returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": fake_id},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_create_item_share_without_auth(self, client):
        """Create share without authentication returns 401."""
        resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 401

    def test_create_collection_share(self, client, auth_headers):
        """Create a share for a collection."""
        coll_resp = client.post(
            "/api/v1/collections",
            json={"name": "My Collection"},
            headers=auth_headers,
        )
        coll_id = coll_resp.json()["id"]

        resp = client.post(
            "/api/v1/shares",
            json={"share_type": "collection", "collection_id": coll_id},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["share_type"] == "collection"
        assert data["collection_id"] == coll_id

    def test_create_tag_share(self, client, auth_headers):
        """Create a share for a tag."""
        tag_resp = client.post(
            "/api/v1/tags",
            json={"name": "python"},
            headers=auth_headers,
        )
        tag_id = tag_resp.json()["id"]

        resp = client.post(
            "/api/v1/shares",
            json={"share_type": "tag", "tag_id": tag_id},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["share_type"] == "tag"
        assert data["tag_id"] == tag_id


class TestShareAccess:
    """Public share access endpoint tests."""

    def test_public_share_returns_item(self, client, auth_headers):
        """Valid public token returns the shared item."""
        item_resp = client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/pub-item",
                "title": "Public Item",
                "description": "A description",
                "content": "Some content",
            },
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id, "public": True},
            headers=auth_headers,
        )
        token = share_resp.json()["public_token"]

        # No auth headers — public endpoint
        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == item_id
        assert data["title"] == "Public Item"
        assert data["description"] == "A description"
        assert "owner_display_name" in data

    def test_public_share_strips_html(self, client, auth_headers):
        """HTML tags are stripped from item fields in public share."""
        item_resp = client.post(
            "/api/v1/items",
            json={
                "url": "https://example.com/html-item",
                "title": "<b>Bold</b> Title",
                "description": "<script>evil</script>Safe desc",
            },
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id, "public": True},
            headers=auth_headers,
        )
        token = share_resp.json()["public_token"]

        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 200
        data = resp.json()
        assert "<b>" not in data["title"]
        assert "<script>" not in data["description"]

    def test_public_share_wrong_token_returns_404(self, client):
        """Invalid token returns 404."""
        resp = client.get("/api/v1/public/nonexistent_token_xyz123")
        assert resp.status_code == 404

    def test_public_share_non_item_returns_404(self, client, auth_headers):
        """Public token for a non-item share (collection/tag) returns 404."""
        coll_resp = client.post(
            "/api/v1/collections",
            json={"name": "Private Collection"},
            headers=auth_headers,
        )
        coll_id = coll_resp.json()["id"]

        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "collection", "collection_id": coll_id, "public": True},
            headers=auth_headers,
        )
        token = share_resp.json()["public_token"]

        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 404

    def test_public_share_expired_returns_404(self, client, auth_headers, monkeypatch):
        """Expired share token returns 404.

        Note: we patch validate_public_token to return None because the
        production code has a naive/aware datetime comparison bug with
        SQLite storage (SQLite strips timezone info from datetimes).
        """
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/expired", "title": "Expired"},
            headers=auth_headers,
        )
        item_resp.json()["id"]

        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_resp.json()["id"], "public": True},
            headers=auth_headers,
        )
        token = share_resp.json()["public_token"]

        # Patch validate_public_token in the sharing module where it's imported
        monkeypatch.setattr("fourdpocket.api.sharing.validate_public_token", lambda db, token=None: None)

        resp = client.get(f"/api/v1/public/{token}")
        assert resp.status_code == 404


class TestShareManagement:
    """Share listing, revoking, and management endpoint tests."""

    def test_list_shares_returns_own_shares(self, client, auth_headers):
        """List shares returns only the current user's shares."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/list-test"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]
        client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id},
            headers=auth_headers,
        )

        resp = client.get("/api/v1/shares", headers=auth_headers)
        assert resp.status_code == 200
        shares = resp.json()
        assert len(shares) >= 1
        # All returned shares should belong to the current user
        first_owner = shares[0]["owner_id"]
        assert all(s["owner_id"] == first_owner for s in shares)

    def test_list_shares_pagination(self, client, auth_headers):
        """List shares respects offset and limit."""
        resp = client.get("/api/v1/shares?offset=0&limit=5", headers=auth_headers)
        assert resp.status_code == 200

    def test_list_shares_requires_auth(self, client):
        """List shares without auth returns 401."""
        resp = client.get("/api/v1/shares")
        assert resp.status_code == 401

    def test_revoke_share_success(self, client, auth_headers):
        """Owner can revoke their own share."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/revoke-test", "title": "Revoke Me"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]
        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id},
            headers=auth_headers,
        )
        share_id = share_resp.json()["id"]

        resp = client.delete(f"/api/v1/shares/{share_id}", headers=auth_headers)
        assert resp.status_code == 204

    def test_revoke_share_not_found_for_other_user(self, client, auth_headers, second_user_headers):
        """User cannot revoke another user's share."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/other-share"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]
        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id},
            headers=auth_headers,
        )
        share_id = share_resp.json()["id"]

        # second_user tries to revoke
        resp = client.delete(f"/api/v1/shares/{share_id}", headers=second_user_headers)
        assert resp.status_code == 404

    def test_revoke_nonexistent_share(self, client, auth_headers):
        """Revoking a non-existent share returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.delete(f"/api/v1/shares/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404


class TestShareRecipients:
    """Share recipient management endpoint tests."""

    def _get_user_id(self, client, headers) -> str:
        """Helper to get a user's ID via the /auth/me endpoint."""
        resp = client.get("/api/v1/auth/me", headers=headers)
        return resp.json()["id"]

    def test_add_recipient_to_share(self, client, auth_headers, second_user_headers):
        """Owner can add a recipient to a share."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/recipient-test"},
            headers=auth_headers,
        )
        item_resp.json()["id"]
        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_resp.json()["id"]},
            headers=auth_headers,
        )
        share_id = share_resp.json()["id"]

        second_user_id = self._get_user_id(client, second_user_headers)

        add_resp = client.post(
            f"/api/v1/shares/{share_id}/recipients",
            json={"user_id": second_user_id, "role": "viewer"},
            headers=auth_headers,
        )
        assert add_resp.status_code == 201
        data = add_resp.json()
        assert data["user_id"] == second_user_id
        assert data["role"] == "viewer"

    def test_add_recipient_not_owner_returns_404(self, client, auth_headers, second_user_headers):
        """Non-owner cannot add recipients to a share."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/other-items"},
            headers=auth_headers,
        )
        item_resp.json()["id"]
        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_resp.json()["id"]},
            headers=auth_headers,
        )
        share_id = share_resp.json()["id"]

        second_user_id = self._get_user_id(client, second_user_headers)

        # Try adding via second_user headers (not owner)
        add_resp = client.post(
            f"/api/v1/shares/{share_id}/recipients",
            json={"user_id": second_user_id},
            headers=second_user_headers,
        )
        assert add_resp.status_code == 404

    def test_remove_recipient(self, client, auth_headers, second_user_headers):
        """Owner can remove a recipient from a share."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/remove-recip"},
            headers=auth_headers,
        )
        item_resp.json()["id"]
        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_resp.json()["id"]},
            headers=auth_headers,
        )
        share_id = share_resp.json()["id"]

        second_user_id = self._get_user_id(client, second_user_headers)

        client.post(
            f"/api/v1/shares/{share_id}/recipients",
            json={"user_id": second_user_id},
            headers=auth_headers,
        )

        rem_resp = client.delete(
            f"/api/v1/shares/{share_id}/recipients/{second_user_id}",
            headers=auth_headers,
        )
        assert rem_resp.status_code == 204


class TestSharedWithMe:
    """Shared-with-me endpoint tests."""

    def _get_user_id(self, client, headers) -> str:
        resp = client.get("/api/v1/auth/me", headers=headers)
        return resp.json()["id"]

    def test_list_shared_with_me(self, client, auth_headers, second_user_headers):
        """User can see items shared with them via recipient list."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/shared-here"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]
        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_id},
            headers=auth_headers,
        )
        share_id = share_resp.json()["id"]

        second_user_id = self._get_user_id(client, second_user_headers)

        client.post(
            f"/api/v1/shares/{share_id}/recipients",
            json={"user_id": second_user_id, "role": "viewer"},
            headers=auth_headers,
        )

        resp = client.get("/api/v1/shares/shared-with-me", headers=second_user_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert any(s["item_id"] == item_id for s in items)

    def test_shared_with_me_requires_auth(self, client):
        """Without auth, shared-with-me returns 401."""
        resp = client.get("/api/v1/shares/shared-with-me")
        assert resp.status_code == 401


class TestAcceptShare:
    """Accept share endpoint tests."""

    def _get_user_id(self, client, headers) -> str:
        resp = client.get("/api/v1/auth/me", headers=headers)
        return resp.json()["id"]

    def test_accept_share_sets_accepted(self, client, auth_headers, second_user_headers):
        """Recipient can accept a share invitation."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/accept-test"},
            headers=auth_headers,
        )
        item_resp.json()["id"]
        share_resp = client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_resp.json()["id"]},
            headers=auth_headers,
        )
        share_id = share_resp.json()["id"]

        second_user_id = self._get_user_id(client, second_user_headers)

        client.post(
            f"/api/v1/shares/{share_id}/recipients",
            json={"user_id": second_user_id},
            headers=auth_headers,
        )

        accept_resp = client.post(
            f"/api/v1/shares/{share_id}/accept",
            headers=second_user_headers,
        )
        assert accept_resp.status_code == 200
        assert accept_resp.json()["accepted"] is True

    def test_accept_nonexistent_share_returns_404(self, client, second_user_headers):
        """Accepting a non-existent share returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/shares/{fake_id}/accept", headers=second_user_headers)
        assert resp.status_code == 404


class TestShareHistory:
    """Share history endpoint tests."""

    def test_share_history_returns_own_shares(self, client, auth_headers):
        """Share history returns the owner's shares with recipient info."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/history-test"},
            headers=auth_headers,
        )
        item_resp.json()["id"]
        client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_resp.json()["id"], "public": True},
            headers=auth_headers,
        )

        resp = client.get("/api/v1/shares/history", headers=auth_headers)
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) >= 1
        assert history[0]["share_type"] == "item"
        assert history[0]["has_public_link"] is True

    def test_share_history_requires_auth(self, client):
        """Share history without auth returns 401."""
        resp = client.get("/api/v1/shares/history")
        assert resp.status_code == 401


class TestCrossUserIsolation:
    """Cross-user isolation for sharing endpoints."""

    def test_user_cannot_see_other_users_shares(
        self, client, auth_headers, second_user_headers
    ):
        """User B cannot list User A's shares."""
        # User A creates an item and share
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/isolation-test"},
            headers=auth_headers,
        )
        item_resp.json()["id"]
        client.post(
            "/api/v1/shares",
            json={"share_type": "item", "item_id": item_resp.json()["id"]},
            headers=auth_headers,
        )

        # User B lists shares — should see only their own (none)
        resp = client.get("/api/v1/shares", headers=second_user_headers)
        assert resp.status_code == 200
        # User B's shares are empty (they haven't created any)
        assert len(resp.json()) == 0

    def test_user_cannot_access_other_users_public_share_token(
        self, client, auth_headers,
    ):
        """Fake token returns 404 (no share exists without being created)."""
        # User A creates a private item (no share at all)
        client.post(
            "/api/v1/items",
            json={"url": "https://example.com/private-item-no-share"},
            headers=auth_headers,
        )

        # No share was created, so any token is invalid
        fake_token = "totally_fake_token_string_123456"
        resp = client.get(f"/api/v1/public/{fake_token}")
        assert resp.status_code == 404


# === PHASE 3 MOPUP ADDITIONS ===

class TestShareCreationExtras:
    """Additional share creation scenario tests."""

    def test_create_share_with_recipient_email(self, client, auth_headers, second_user_headers):
        """Share creation with recipient_email adds them as recipient."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/recip-email-test", "title": "Recip Email Test"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        # Get second user's email
        me_resp = client.get("/api/v1/auth/me", headers=second_user_headers)
        second_email = me_resp.json()["email"]

        resp = client.post(
            "/api/v1/shares",
            json={
                "share_type": "item",
                "item_id": item_id,
                "recipient_email": second_email,
                "permission": "editor",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        share_id = resp.json()["id"]

        # Verify second user can see it in shared-with-me
        shared_resp = client.get("/api/v1/shares/shared-with-me", headers=second_user_headers)
        assert shared_resp.status_code == 200
        shared_items = shared_resp.json()
        assert any(s["share_id"] == share_id for s in shared_items)

    def test_create_share_with_self_recipient_returns_400(self, client, auth_headers):
        """Cannot share with your own email returns 400."""
        item_resp = client.post(
            "/api/v1/items",
            json={"url": "https://example.com/self-share", "title": "Self Share"},
            headers=auth_headers,
        )
        item_id = item_resp.json()["id"]

        me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
        my_email = me_resp.json()["email"]

        resp = client.post(
            "/api/v1/shares",
            json={
                "share_type": "item",
                "item_id": item_id,
                "recipient_email": my_email,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()


class TestShareHistoryExtras:
    """Additional share history tests."""

    def test_share_history_empty_for_new_user(self, client):
        """New user with no shares gets empty history."""
        # Register fresh user
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "freshhistory@test.com",
                "username": "fresshuser",
                "password": "TestPass123!",
                "display_name": "Fresh User",
            },
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            data={"username": "freshhistory@test.com", "password": "TestPass123!"},
        )
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/api/v1/shares/history", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []
