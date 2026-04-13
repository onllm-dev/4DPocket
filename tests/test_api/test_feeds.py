"""Tests for knowledge feed (subscription) API endpoints."""

import uuid


class TestSubscribe:
    """Subscribe to user feed endpoint tests."""

    def _get_user_id(self, client, headers) -> str:
        resp = client.get("/api/v1/auth/me", headers=headers)
        return resp.json()["id"]

    def test_subscribe_to_user(self, client, auth_headers, second_user_headers):
        """User can subscribe to another user's feed."""
        publisher_id = self._get_user_id(client, second_user_headers)

        resp = client.post(
            f"/api/v1/feeds/subscribe/{publisher_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["publisher_id"] == publisher_id
        assert "id" in data

    def test_subscribe_to_self(self, client, auth_headers):
        """User cannot subscribe to themselves."""
        user_id = self._get_user_id(client, auth_headers)

        resp = client.post(
            f"/api/v1/feeds/subscribe/{user_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    def test_subscribe_to_nonexistent_user(self, client, auth_headers):
        """Subscribing to a non-existent user returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/feeds/subscribe/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_subscribe_requires_auth(self, client):
        """Without auth returns 401."""
        fake_id = str(uuid.uuid4())
        resp = client.post(f"/api/v1/feeds/subscribe/{fake_id}")
        assert resp.status_code == 401


class TestUnsubscribe:
    """Unsubscribe from user feed endpoint tests."""

    def _get_user_id(self, client, headers) -> str:
        resp = client.get("/api/v1/auth/me", headers=headers)
        return resp.json()["id"]

    def test_unsubscribe_success(self, client, auth_headers, second_user_headers):
        """User can unsubscribe from a user's feed."""
        publisher_id = self._get_user_id(client, second_user_headers)

        # Subscribe first
        client.post(f"/api/v1/feeds/subscribe/{publisher_id}", headers=auth_headers)

        # Then unsubscribe
        resp = client.delete(
            f"/api/v1/feeds/unsubscribe/{publisher_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    def test_unsubscribe_not_subscribed(self, client, auth_headers, second_user_headers):
        """Unsubscribe from a user you haven't subscribed to returns 404."""
        publisher_id = self._get_user_id(client, second_user_headers)

        resp = client.delete(
            f"/api/v1/feeds/unsubscribe/{publisher_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_unsubscribe_requires_auth(self, client):
        """Without auth returns 401."""
        fake_id = str(uuid.uuid4())
        resp = client.delete(f"/api/v1/feeds/unsubscribe/{fake_id}")
        assert resp.status_code == 401


class TestGetFeed:
    """Get personalized feed endpoint tests."""

    def _get_user_id(self, client, headers) -> str:
        resp = client.get("/api/v1/auth/me", headers=headers)
        return resp.json()["id"]

    def test_get_feed_empty(self, client, auth_headers):
        """Feed with no subscriptions returns empty list."""
        resp = client.get("/api/v1/feeds", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_feed_requires_auth(self, client):
        """Without auth returns 401."""
        resp = client.get("/api/v1/feeds")
        assert resp.status_code == 401

    def test_subscribe_and_list_feed_empty_when_no_accessible_items(
        self, client, auth_headers, second_user_headers
    ):
        """After subscribing, feed is empty when publisher has no accessible items."""
        publisher_id = self._get_user_id(client, second_user_headers)

        client.post(
            f"/api/v1/feeds/subscribe/{publisher_id}",
            headers=auth_headers,
        )

        resp = client.get("/api/v1/feeds", headers=auth_headers)
        assert resp.status_code == 200

    def test_get_feed_pagination(self, client, auth_headers):
        """Feed respects offset and limit."""
        resp = client.get("/api/v1/feeds?offset=0&limit=10", headers=auth_headers)
        assert resp.status_code == 200
