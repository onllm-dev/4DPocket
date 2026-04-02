"""CRUD tests for collections endpoints."""


def test_create_collection(client, auth_headers):
    response = client.post(
        "/api/v1/collections",
        json={"name": "My Reading List", "description": "Articles to read"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Reading List"
    assert data["description"] == "Articles to read"
    assert "id" in data
    assert "user_id" in data
    assert data["is_public"] is False


def test_list_collections_returns_users_collections(client, auth_headers, second_user_headers):
    client.post("/api/v1/collections", json={"name": "Collection A"}, headers=auth_headers)
    client.post("/api/v1/collections", json={"name": "Collection B"}, headers=auth_headers)
    client.post("/api/v1/collections", json={"name": "Collection C"}, headers=second_user_headers)

    response = client.get("/api/v1/collections", headers=auth_headers)
    assert response.status_code == 200
    collections = response.json()
    assert len(collections) == 2
    names = {col["name"] for col in collections}
    assert "Collection A" in names
    assert "Collection B" in names
    assert "Collection C" not in names


def test_get_collection_by_id(client, auth_headers):
    create_resp = client.post(
        "/api/v1/collections",
        json={"name": "Find Me"},
        headers=auth_headers,
    )
    collection_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == collection_id


def test_get_nonexistent_collection_returns_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000004"
    response = client.get(f"/api/v1/collections/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_update_collection(client, auth_headers):
    create_resp = client.post(
        "/api/v1/collections",
        json={"name": "Original Name"},
        headers=auth_headers,
    )
    collection_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/collections/{collection_id}",
        json={"name": "Updated Name", "description": "Now has a description"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Now has a description"


def test_delete_collection(client, auth_headers):
    create_resp = client.post(
        "/api/v1/collections",
        json={"name": "To Delete"},
        headers=auth_headers,
    )
    collection_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_add_items_to_collection(client, auth_headers):
    collection_resp = client.post(
        "/api/v1/collections",
        json={"name": "With Items"},
        headers=auth_headers,
    )
    collection_id = collection_resp.json()["id"]

    item1_resp = client.post("/api/v1/items", json={"url": "https://item1.com"}, headers=auth_headers)
    item2_resp = client.post("/api/v1/items", json={"url": "https://item2.com"}, headers=auth_headers)
    item1_id = item1_resp.json()["id"]
    item2_id = item2_resp.json()["id"]

    response = client.post(
        f"/api/v1/collections/{collection_id}/items",
        json={"item_ids": [item1_id, item2_id]},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data["added"]) == 2


def test_list_collection_items(client, auth_headers):
    collection_resp = client.post(
        "/api/v1/collections",
        json={"name": "List Items"},
        headers=auth_headers,
    )
    collection_id = collection_resp.json()["id"]

    item1_resp = client.post("/api/v1/items", json={"url": "https://a.com"}, headers=auth_headers)
    item2_resp = client.post("/api/v1/items", json={"url": "https://b.com"}, headers=auth_headers)
    item1_id = item1_resp.json()["id"]
    item2_id = item2_resp.json()["id"]

    client.post(
        f"/api/v1/collections/{collection_id}/items",
        json={"item_ids": [item1_id, item2_id]},
        headers=auth_headers,
    )

    response = client.get(f"/api/v1/collections/{collection_id}/items", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 2
    ids = {item["id"] for item in items}
    assert item1_id in ids
    assert item2_id in ids


def test_remove_item_from_collection(client, auth_headers):
    collection_resp = client.post(
        "/api/v1/collections",
        json={"name": "Remove Test"},
        headers=auth_headers,
    )
    collection_id = collection_resp.json()["id"]

    item_resp = client.post("/api/v1/items", json={"url": "https://remove.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    client.post(
        f"/api/v1/collections/{collection_id}/items",
        json={"item_ids": [item_id]},
        headers=auth_headers,
    )

    response = client.delete(
        f"/api/v1/collections/{collection_id}/items/{item_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204

    list_resp = client.get(f"/api/v1/collections/{collection_id}/items", headers=auth_headers)
    assert list_resp.json() == []


def test_reorder_collection_items(client, auth_headers):
    collection_resp = client.post(
        "/api/v1/collections",
        json={"name": "Reorder Test"},
        headers=auth_headers,
    )
    collection_id = collection_resp.json()["id"]

    item1_resp = client.post("/api/v1/items", json={"url": "https://first.com"}, headers=auth_headers)
    item2_resp = client.post("/api/v1/items", json={"url": "https://second.com"}, headers=auth_headers)
    item1_id = item1_resp.json()["id"]
    item2_id = item2_resp.json()["id"]

    client.post(
        f"/api/v1/collections/{collection_id}/items",
        json={"item_ids": [item1_id, item2_id]},
        headers=auth_headers,
    )

    response = client.put(
        f"/api/v1/collections/{collection_id}/items/reorder",
        json={"items": [{"item_id": item1_id, "position": 1}, {"item_id": item2_id, "position": 0}]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "reordered"

    list_resp = client.get(f"/api/v1/collections/{collection_id}/items", headers=auth_headers)
    items = list_resp.json()
    assert len(items) == 2
    assert items[0]["id"] == item2_id
    assert items[1]["id"] == item1_id


def test_user_scoping_collection_not_accessible_to_other_user(client, auth_headers, second_user_headers):
    create_resp = client.post(
        "/api/v1/collections",
        json={"name": "Private Collection"},
        headers=auth_headers,
    )
    collection_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/collections/{collection_id}", headers=second_user_headers)
    assert response.status_code == 404
