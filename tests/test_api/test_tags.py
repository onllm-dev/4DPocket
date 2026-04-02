"""CRUD tests for tags endpoints."""


def test_create_tag(client, auth_headers):
    response = client.post(
        "/api/v1/tags",
        json={"name": "Python"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Python"
    assert data["slug"] == "python"
    assert "id" in data
    assert "user_id" in data
    assert data["usage_count"] == 0


def test_create_tag_slug_auto_generated(client, auth_headers):
    response = client.post(
        "/api/v1/tags",
        json={"name": "Machine Learning"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "machine-learning"


def test_create_duplicate_tag_returns_409(client, auth_headers):
    client.post("/api/v1/tags", json={"name": "Duplicate"}, headers=auth_headers)
    response = client.post("/api/v1/tags", json={"name": "Duplicate"}, headers=auth_headers)
    assert response.status_code == 409


def test_list_tags_returns_users_tags(client, auth_headers, second_user_headers):
    client.post("/api/v1/tags", json={"name": "Tag A"}, headers=auth_headers)
    client.post("/api/v1/tags", json={"name": "Tag B"}, headers=auth_headers)
    client.post("/api/v1/tags", json={"name": "Tag C"}, headers=second_user_headers)

    response = client.get("/api/v1/tags", headers=auth_headers)
    assert response.status_code == 200
    tags = response.json()
    assert len(tags) == 2
    names = {tag["name"] for tag in tags}
    assert "Tag A" in names
    assert "Tag B" in names
    assert "Tag C" not in names


def test_get_tag_by_id(client, auth_headers):
    create_resp = client.post("/api/v1/tags", json={"name": "FindMe"}, headers=auth_headers)
    tag_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/tags/{tag_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == tag_id


def test_get_nonexistent_tag_returns_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000003"
    response = client.get(f"/api/v1/tags/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_update_tag_name_updates_slug(client, auth_headers):
    create_resp = client.post("/api/v1/tags", json={"name": "OldName"}, headers=auth_headers)
    tag_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/tags/{tag_id}",
        json={"name": "New Name"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["slug"] == "new-name"


def test_delete_tag(client, auth_headers):
    create_resp = client.post("/api/v1/tags", json={"name": "DeleteMe"}, headers=auth_headers)
    tag_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/tags/{tag_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/v1/tags/{tag_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_create_tag_with_parent(client, auth_headers):
    parent_resp = client.post("/api/v1/tags", json={"name": "Parent"}, headers=auth_headers)
    parent_id = parent_resp.json()["id"]

    response = client.post(
        "/api/v1/tags",
        json={"name": "Child", "parent_id": parent_id},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["parent_id"] == parent_id


def test_list_items_for_tag(client, auth_headers):
    tag_resp = client.post("/api/v1/tags", json={"name": "Tech"}, headers=auth_headers)
    tag_id = tag_resp.json()["id"]

    item_resp = client.post("/api/v1/items", json={"url": "https://tech.example.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    client.post(f"/api/v1/items/{item_id}/tags?tag_id={tag_id}", headers=auth_headers)

    response = client.get(f"/api/v1/tags/{tag_id}/items", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["id"] == item_id


def test_list_items_for_tag_empty(client, auth_headers):
    tag_resp = client.post("/api/v1/tags", json={"name": "Empty"}, headers=auth_headers)
    tag_id = tag_resp.json()["id"]

    response = client.get(f"/api/v1/tags/{tag_id}/items", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []
