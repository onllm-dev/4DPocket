"""CRUD tests for item-link endpoints."""




def _create_item(client, auth_headers, url="https://example.com/article"):
    resp = client.post("/api/v1/items", json={"url": url}, headers=auth_headers)
    return resp.json()["id"]


def test_create_item_link(client, auth_headers):
    """Add a link to an item."""
    item_id = _create_item(client, auth_headers)

    response = client.post(
        f"/api/v1/items/{item_id}/links",
        json={"url": "https://example.com/related", "title": "Related Article", "position": 0},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["item_id"] == item_id
    assert data["url"] == "https://example.com/related"
    assert data["title"] == "Related Article"
    assert data["domain"] == "example.com"
    assert "id" in data
    assert "created_at" in data


def test_create_item_link_auto_extracts_domain(client, auth_headers):
    """Domain is auto-extracted from URL if not provided."""
    item_id = _create_item(client, auth_headers)

    response = client.post(
        f"/api/v1/items/{item_id}/links",
        json={"url": "https://github.com/user/repo"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["domain"] == "github.com"


def test_create_item_link_rejects_dangerous_scheme(client, auth_headers):
    """javascript:, data:, vbscript: schemes are rejected."""
    item_id = _create_item(client, auth_headers)

    for scheme in ("javascript:alert(1)", "data:text/html,<script>", "vbscript:msgbox"):
        response = client.post(
            f"/api/v1/items/{item_id}/links",
            json={"url": scheme},
            headers=auth_headers,
        )
        assert response.status_code == 422, f"Expected 422 for scheme: {scheme}"


def test_create_item_link_with_custom_domain(client, auth_headers):
    """Custom domain can override auto-extracted value."""
    item_id = _create_item(client, auth_headers)

    response = client.post(
        f"/api/v1/items/{item_id}/links",
        json={"url": "https://example.com/page", "domain": "custom.domain.com"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["domain"] == "custom.domain.com"


def test_list_item_links(client, auth_headers):
    """List all links for an item."""
    item_id = _create_item(client, auth_headers)

    client.post(
        f"/api/v1/items/{item_id}/links",
        json={"url": "https://example.com/link1", "position": 0},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/items/{item_id}/links",
        json={"url": "https://example.com/link2", "position": 1},
        headers=auth_headers,
    )

    response = client.get(f"/api/v1/items/{item_id}/links", headers=auth_headers)
    assert response.status_code == 200
    links = response.json()
    assert len(links) == 2
    # Ordered by position
    assert links[0]["position"] < links[1]["position"]


def test_list_item_links_404_for_nonexistent_item(client, auth_headers):
    """Listing links for nonexistent item returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.get(f"/api/v1/items/{fake_id}/links", headers=auth_headers)
    assert response.status_code == 404


def test_delete_item_link(client, auth_headers):
    """Delete a link from an item."""
    item_id = _create_item(client, auth_headers)

    create_resp = client.post(
        f"/api/v1/items/{item_id}/links",
        json={"url": "https://example.com/to-delete"},
        headers=auth_headers,
    )
    link_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/items/{item_id}/links/{link_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    list_resp = client.get(f"/api/v1/items/{item_id}/links", headers=auth_headers)
    assert all(link["id"] != link_id for link in list_resp.json())


def test_delete_item_link_404_for_nonexistent_link(client, auth_headers):
    """Deleting nonexistent link returns 404."""
    item_id = _create_item(client, auth_headers)
    fake_link_id = "00000000-0000-0000-0000-000000000002"

    delete_resp = client.delete(f"/api/v1/items/{item_id}/links/{fake_link_id}", headers=auth_headers)
    assert delete_resp.status_code == 404


def test_delete_item_link_404_for_wrong_item(client, auth_headers):
    """Link belonging to different item returns 404 when accessed via wrong item."""
    item_id_a = _create_item(client, auth_headers)
    item_id_b = _create_item(client, auth_headers, url="https://example.com/other-article")

    create_resp = client.post(
        f"/api/v1/items/{item_id_a}/links",
        json={"url": "https://example.com/link"},
        headers=auth_headers,
    )
    link_id = create_resp.json()["id"]

    # Trying to delete via item_id_b instead of item_id_a returns 404
    delete_resp = client.delete(f"/api/v1/items/{item_id_b}/links/{link_id}", headers=auth_headers)
    assert delete_resp.status_code == 404


def test_reorder_item_links(client, auth_headers):
    """Reorder links by providing link_ids in desired order."""
    item_id = _create_item(client, auth_headers)

    client.post(f"/api/v1/items/{item_id}/links", json={"url": "https://a.com/1", "position": 0}, headers=auth_headers)
    client.post(f"/api/v1/items/{item_id}/links", json={"url": "https://a.com/2", "position": 1}, headers=auth_headers)
    client.post(f"/api/v1/items/{item_id}/links", json={"url": "https://a.com/3", "position": 2}, headers=auth_headers)

    list_resp = client.get(f"/api/v1/items/{item_id}/links", headers=auth_headers)
    links = list_resp.json()
    link_ids = [link["id"] for link in links]

    # Reverse the order
    reversed_ids = list(reversed(link_ids))
    reorder_resp = client.put(
        f"/api/v1/items/{item_id}/links/reorder",
        json={"link_ids": reversed_ids},
        headers=auth_headers,
    )
    assert reorder_resp.status_code == 200

    verify_resp = client.get(f"/api/v1/items/{item_id}/links", headers=auth_headers)
    verified_links = verify_resp.json()
    assert [link["id"] for link in verified_links] == reversed_ids


def test_reorder_item_links_404_for_nonexistent_item(client, auth_headers):
    """Reorder on nonexistent item returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.put(
        f"/api/v1/items/{fake_id}/links/reorder",
        json={"link_ids": []},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_user_scoping_links_not_visible_to_other_user(client, auth_headers, second_user_headers):
    """Links from user A are not visible to user B."""
    item_id = _create_item(client, auth_headers)

    client.post(
        f"/api/v1/items/{item_id}/links",
        json={"url": "https://example.com/my-link"},
        headers=auth_headers,
    )

    list_resp = client.get(f"/api/v1/items/{item_id}/links", headers=second_user_headers)
    assert list_resp.status_code == 404


def test_item_link_401_without_auth(client):
    """Endpoints require authentication."""
    fake_id = "00000000-0000-0000-0000-000000000001"
    response = client.get(f"/api/v1/items/{fake_id}/links")
    assert response.status_code == 401
