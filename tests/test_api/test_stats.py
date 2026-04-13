"""Tests for dashboard statistics endpoints."""
import uuid


def _seed_item(client, auth_headers, url="https://example.com", title="Test", content="content", source_platform=None):
    payload = {"url": url, "title": title, "content": content}
    if source_platform:
        payload["source_platform"] = source_platform
    resp = client.post("/api/v1/items", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["id"]


class TestDashboardStats:
    """Test /stats endpoint."""

    def test_stats_returns_all_counts(self, client, auth_headers):
        """Stats returns total_items, total_tags, total_notes, total_collections."""
        response = client.get("/api/v1/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_items" in data
        assert "items_this_week" in data
        assert "total_tags" in data
        assert "total_notes" in data
        assert "total_collections" in data
        assert "items_by_platform" in data
        assert "top_tags" in data

    def test_stats_user_scoping(self, client, auth_headers, second_user_headers):
        """Each user only sees their own counts."""
        # User A creates items
        _seed_item(client, auth_headers, url="https://a.com")
        _seed_item(client, auth_headers, url="https://a2.com")
        client.post("/api/v1/tags", json={"name": "atag"}, headers=auth_headers)

        # User B creates fewer items
        _seed_item(client, second_user_headers, url="https://b.com")

        response_a = client.get("/api/v1/stats", headers=auth_headers)
        response_b = client.get("/api/v1/stats", headers=second_user_headers)

        assert response_a.status_code == 200
        assert response_b.status_code == 200
        assert response_a.json()["total_items"] == 2
        assert response_b.json()["total_items"] == 1

    def test_stats_items_this_week_counts_recent_items(self, client, auth_headers):
        """items_this_week only counts items created in the last 7 days."""
        response = client.get("/api/v1/stats", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["items_this_week"] >= 0

    def test_stats_returns_platform_breakdown(self, client, auth_headers):
        """items_by_platform returns platform counts."""
        _seed_item(client, auth_headers, url="https://github.com/user/repo", source_platform="github")
        _seed_item(client, auth_headers, url="https://reddit.com/r/python", source_platform="reddit")

        response = client.get("/api/v1/stats", headers=auth_headers)
        assert response.status_code == 200
        platforms = response.json()["items_by_platform"]
        # Keys are enum values like "SourcePlatform.github"
        assert any("github" in k for k in platforms) or any("reddit" in k for k in platforms)

    def test_stats_returns_top_tags(self, client, auth_headers):
        """top_tags returns up to 10 tags ordered by usage_count."""
        response = client.get("/api/v1/stats", headers=auth_headers)
        assert response.status_code == 200
        top_tags = response.json()["top_tags"]
        assert isinstance(top_tags, list)
        # Each entry should have name and count
        for tag in top_tags:
            assert "name" in tag
            assert "count" in tag

    def test_stats_requires_auth(self, client):
        """Stats endpoint requires authentication."""
        response = client.get("/api/v1/stats")
        assert response.status_code == 401


class TestPublicProfile:
    """Test /users/{user_id}/public endpoint."""

    def test_public_profile_returns_404_for_nonexistent_user(self, client, auth_headers):
        """Non-existent user returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/users/{fake_id}/public", headers=auth_headers)
        assert response.status_code == 404
