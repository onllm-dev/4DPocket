"""Tests for user settings endpoints."""


class TestGetUserSettings:
    """Test GET /settings endpoint."""

    def test_get_settings_returns_defaults(self, client, auth_headers):
        """Returns settings with defaults merged from schema."""
        response = client.get("/api/v1/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "auto_tag" in data
        assert "auto_summarize" in data
        assert "tag_confidence_threshold" in data
        assert "media_download" in data
        assert "theme" in data
        assert "view_mode" in data

    def test_get_settings_requires_auth(self, client):
        """Settings endpoint requires authentication."""
        response = client.get("/api/v1/settings")
        assert response.status_code == 401


class TestUpdateUserSettings:
    """Test PATCH /settings endpoint."""

    def test_update_settings_returns_merged(self, client, auth_headers):
        """Updating some fields returns all settings with updates applied."""
        response = client.patch(
            "/api/v1/settings",
            json={"auto_tag": False, "theme": "dark"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auto_tag"] is False
        assert data["theme"] == "dark"
        # Other fields should remain at defaults
        assert data["auto_summarize"] is True

    def test_update_all_settings_fields(self, client, auth_headers):
        """All settings fields can be updated."""
        response = client.patch(
            "/api/v1/settings",
            json={
                "auto_tag": False,
                "auto_summarize": False,
                "tag_confidence_threshold": 0.5,
                "media_download": False,
                "default_share_mode": "public",
                "theme": "light",
                "view_mode": "list",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auto_tag"] is False
        assert data["auto_summarize"] is False
        assert data["tag_confidence_threshold"] == 0.5
        assert data["media_download"] is False
        assert data["default_share_mode"] == "public"
        assert data["theme"] == "light"
        assert data["view_mode"] == "list"

    def test_update_settings_user_scoping(self, client, auth_headers, second_user_headers):
        """Each user's settings are independent."""
        # User A updates theme
        client.patch("/api/v1/settings", json={"theme": "dark"}, headers=auth_headers)

        # User B updates theme to something else
        client.patch("/api/v1/settings", json={"theme": "light"}, headers=second_user_headers)

        # Verify each sees their own setting
        resp_a = client.get("/api/v1/settings", headers=auth_headers)
        resp_b = client.get("/api/v1/settings", headers=second_user_headers)

        assert resp_a.json()["theme"] == "dark"
        assert resp_b.json()["theme"] == "light"

    def test_update_settings_requires_auth(self, client):
        """PATCH settings requires authentication."""
        response = client.patch("/api/v1/settings", json={"theme": "dark"})
        assert response.status_code == 401
