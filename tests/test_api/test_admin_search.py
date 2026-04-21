"""Admin search settings endpoint tests."""


def test_admin_get_search_settings(client, auth_headers):
    """Admin can read search settings with env-default values."""
    response = client.get("/api/v1/admin/search-settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "graph_ranker_enabled" in data
    assert "graph_ranker_hop_decay" in data
    assert "graph_ranker_top_k" in data
    # Default is on
    assert data["graph_ranker_enabled"] is True


def test_admin_can_disable_graph_ranker(client, auth_headers):
    """Admin override disables graph ranker; override takes precedence over env."""
    response = client.patch(
        "/api/v1/admin/search-settings",
        json={"graph_ranker_enabled": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["graph_ranker_enabled"] is False

    # Subsequent GET returns the override
    response = client.get("/api/v1/admin/search-settings", headers=auth_headers)
    assert response.json()["graph_ranker_enabled"] is False


def test_admin_can_re_enable_graph_ranker(client, auth_headers):
    """Flipping the flag back on works."""
    client.patch(
        "/api/v1/admin/search-settings",
        json={"graph_ranker_enabled": False},
        headers=auth_headers,
    )
    response = client.patch(
        "/api/v1/admin/search-settings",
        json={"graph_ranker_enabled": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["graph_ranker_enabled"] is True


def test_admin_can_update_hop_decay_and_top_k(client, auth_headers):
    """Numeric knobs update and clamp to safe bounds."""
    response = client.patch(
        "/api/v1/admin/search-settings",
        json={"graph_ranker_hop_decay": 0.3, "graph_ranker_top_k": 25},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["graph_ranker_hop_decay"] == 0.3
    assert data["graph_ranker_top_k"] == 25


def test_admin_search_settings_clamps_out_of_range(client, auth_headers):
    """Out-of-range inputs are clamped server-side."""
    response = client.patch(
        "/api/v1/admin/search-settings",
        json={"graph_ranker_hop_decay": 5.0, "graph_ranker_top_k": 9999},
        headers=auth_headers,
    )
    data = response.json()
    assert data["graph_ranker_hop_decay"] == 1.0
    assert data["graph_ranker_top_k"] == 500


def test_non_admin_cannot_access_search_settings(client, auth_headers, second_user_headers):
    """Non-admin users cannot read or write search settings."""
    response = client.get("/api/v1/admin/search-settings", headers=second_user_headers)
    assert response.status_code == 403

    response = client.patch(
        "/api/v1/admin/search-settings",
        json={"graph_ranker_enabled": False},
        headers=second_user_headers,
    )
    assert response.status_code == 403
