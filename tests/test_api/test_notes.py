"""CRUD tests for notes endpoints."""


def test_create_standalone_note(client, auth_headers):
    response = client.post(
        "/api/v1/notes",
        json={"title": "My Note", "content": "Some content here"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My Note"
    assert data["content"] == "Some content here"
    assert data["item_id"] is None
    assert "id" in data
    assert "user_id" in data
    assert "created_at" in data


def test_list_notes_returns_users_notes(client, auth_headers, second_user_headers):
    client.post("/api/v1/notes", json={"content": "Note A"}, headers=auth_headers)
    client.post("/api/v1/notes", json={"content": "Note B"}, headers=auth_headers)
    client.post("/api/v1/notes", json={"content": "Note C"}, headers=second_user_headers)

    response = client.get("/api/v1/notes", headers=auth_headers)
    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 2
    contents = {note["content"] for note in notes}
    assert "Note A" in contents
    assert "Note B" in contents
    assert "Note C" not in contents


def test_get_note_by_id(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Findable note"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == note_id


def test_get_nonexistent_note_returns_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = client.get(f"/api/v1/notes/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_update_note_content(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notes",
        json={"title": "Original", "content": "Original content"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/v1/notes/{note_id}",
        json={"content": "Updated content"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Updated content"


def test_delete_note(client, auth_headers):
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "To be deleted"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_attach_note_to_item(client, auth_headers):
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        f"/api/v1/items/{item_id}/notes",
        json={"title": "Attached Note", "content": "Note attached to item"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["item_id"] == item_id
    assert data["content"] == "Note attached to item"


def test_list_item_notes(client, auth_headers):
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    client.post(f"/api/v1/items/{item_id}/notes", json={"content": "First note"}, headers=auth_headers)
    client.post(f"/api/v1/items/{item_id}/notes", json={"content": "Second note"}, headers=auth_headers)

    response = client.get(f"/api/v1/items/{item_id}/notes", headers=auth_headers)
    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 2
    assert all(note["item_id"] == item_id for note in notes)


def test_user_scoping_notes_not_visible_to_other_user(client, auth_headers, second_user_headers):
    create_resp = client.post(
        "/api/v1/notes",
        json={"content": "Private note"},
        headers=auth_headers,
    )
    note_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/notes/{note_id}", headers=second_user_headers)
    assert response.status_code == 404

    list_resp = client.get("/api/v1/notes", headers=second_user_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 0
