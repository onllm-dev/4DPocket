"""Admin AI settings endpoint tests."""


def test_admin_get_ai_settings(client, auth_headers):
    """Admin can read AI settings."""
    response = client.get("/api/v1/admin/ai-settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "chat_provider" in data
    assert "auto_tag" in data
    assert "auto_summarize" in data
    assert "sync_enrichment" in data


def test_admin_update_ai_settings(client, auth_headers):
    """Admin can update AI settings."""
    response = client.patch(
        "/api/v1/admin/ai-settings",
        json={"chat_provider": "nvidia", "auto_tag": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["chat_provider"] == "nvidia"
    assert data["auto_tag"] is False


def test_admin_ai_settings_masks_keys(client, auth_headers):
    """API keys should be masked in the response."""
    # Set a key
    client.patch(
        "/api/v1/admin/ai-settings",
        json={"nvidia_api_key": "nvapi-1234567890abcdef"},
        headers=auth_headers,
    )
    # Read it back
    response = client.get("/api/v1/admin/ai-settings", headers=auth_headers)
    data = response.json()
    # Key should be masked
    if data.get("nvidia_api_key"):
        assert "..." in data["nvidia_api_key"]
        assert "1234567890abcdef" not in data["nvidia_api_key"]


def test_admin_ai_custom_provider(client, auth_headers):
    """Admin can configure custom provider."""
    response = client.patch(
        "/api/v1/admin/ai-settings",
        json={
            "chat_provider": "custom",
            "custom_base_url": "https://api.example.com/v1",
            "custom_api_key": "sk-test-key-12345678",
            "custom_model": "test-model",
            "custom_api_type": "anthropic",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["chat_provider"] == "custom"
    assert data["custom_base_url"] == "https://api.example.com/v1"
    assert data["custom_model"] == "test-model"
    assert data["custom_api_type"] == "anthropic"
    # Key should be masked
    assert "..." in data["custom_api_key"]


def test_non_admin_cannot_access_ai_settings(client, auth_headers, second_user_headers):
    """Non-admin users cannot access AI settings."""
    # auth_headers registers the first user (admin), second_user_headers is a regular user
    response = client.get("/api/v1/admin/ai-settings", headers=second_user_headers)
    assert response.status_code == 403
