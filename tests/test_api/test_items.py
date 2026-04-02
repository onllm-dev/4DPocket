"""CRUD tests for knowledge items endpoints."""


def test_create_item_with_url(client, auth_headers):
    response = client.post(
        "/api/v1/items",
        json={"url": "https://example.com/article", "title": "Example Article"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "https://example.com/article"
    assert data["title"] == "Example Article"
    assert data["item_type"] == "url"
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data


def test_create_item_with_content(client, auth_headers):
    response = client.post(
        "/api/v1/items",
        json={
            "title": "My Note",
            "content": "Some note content here",
            "item_type": "note",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My Note"
    assert data["content"] == "Some note content here"
    assert data["item_type"] == "note"


def test_list_items_returns_users_items(client, auth_headers, second_user_headers):
    # Create items for user 1
    client.post("/api/v1/items", json={"url": "https://a.com"}, headers=auth_headers)
    client.post("/api/v1/items", json={"url": "https://b.com"}, headers=auth_headers)
    # Create item for user 2
    client.post("/api/v1/items", json={"url": "https://c.com"}, headers=second_user_headers)

    response = client.get("/api/v1/items", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    urls = {item["url"] for item in items}
    assert "https://a.com" in urls
    assert "https://b.com" in urls
    assert "https://c.com" not in urls


def test_list_items_pagination(client, auth_headers):
    for i in range(5):
        client.post("/api/v1/items", json={"url": f"https://example.com/{i}"}, headers=auth_headers)

    response = client.get("/api/v1/items?offset=0&limit=3", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 3

    response = client.get("/api/v1/items?offset=3&limit=3", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_item_by_id(client, auth_headers):
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com", "title": "Test"},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == item_id


def test_get_nonexistent_item_returns_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000001"
    response = client.get(f"/api/v1/items/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_update_item(client, auth_headers):
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com", "title": "Original Title"},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/items/{item_id}",
        json={"title": "Updated Title", "is_favorite": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["is_favorite"] is True


def test_delete_item(client, auth_headers):
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/v1/items/{item_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_user_scoping_other_user_cannot_get_item(client, auth_headers, second_user_headers):
    create_resp = client.post(
        "/api/v1/items",
        json={"url": "https://private.com"},
        headers=auth_headers,
    )
    item_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/items/{item_id}", headers=second_user_headers)
    assert response.status_code == 404


def test_filter_by_item_type(client, auth_headers):
    client.post("/api/v1/items", json={"url": "https://example.com", "item_type": "url"}, headers=auth_headers)
    client.post("/api/v1/items", json={"title": "Note", "content": "text", "item_type": "note"}, headers=auth_headers)

    response = client.get("/api/v1/items?item_type=note", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert all(item["item_type"] == "note" for item in items)


def test_filter_by_source_platform(client, auth_headers):
    client.post(
        "/api/v1/items",
        json={"url": "https://github.com/user/repo", "source_platform": "github"},
        headers=auth_headers,
    )
    client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )

    response = client.get("/api/v1/items?source_platform=github", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    assert all(item["source_platform"] == "github" for item in items)


def test_filter_by_is_favorite(client, auth_headers):
    create_resp = client.post("/api/v1/items", json={"url": "https://example.com"}, headers=auth_headers)
    item_id = create_resp.json()["id"]
    client.patch(f"/api/v1/items/{item_id}", json={"is_favorite": True}, headers=auth_headers)

    client.post("/api/v1/items", json={"url": "https://other.com"}, headers=auth_headers)

    response = client.get("/api/v1/items?is_favorite=true", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["is_favorite"] is True


def test_add_tag_to_item(client, auth_headers):
    item_resp = client.post("/api/v1/items", json={"url": "https://example.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    tag_resp = client.post("/api/v1/tags", json={"name": "Python"}, headers=auth_headers)
    tag_id = tag_resp.json()["id"]

    response = client.post(
        f"/api/v1/items/{item_id}/tags?tag_id={tag_id}",
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["item_id"] == item_id
    assert data["tag_id"] == tag_id


def test_remove_tag_from_item(client, auth_headers):
    item_resp = client.post("/api/v1/items", json={"url": "https://example.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    tag_resp = client.post("/api/v1/tags", json={"name": "RemoveMe"}, headers=auth_headers)
    tag_id = tag_resp.json()["id"]

    client.post(f"/api/v1/items/{item_id}/tags?tag_id={tag_id}", headers=auth_headers)

    response = client.delete(f"/api/v1/items/{item_id}/tags/{tag_id}", headers=auth_headers)
    assert response.status_code == 204
