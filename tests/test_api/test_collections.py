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


# === PHASE 0C MOPUP ADDITIONS ===

def test_update_collection_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000004"
    response = client.patch(
        f"/api/v1/collections/{fake_id}",
        json={"name": "New Name"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_delete_collection_404(client, auth_headers):
    fake_id = "00000000-0000-0000-0000-000000000004"
    response = client.delete(f"/api/v1/collections/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_collection_cascade(client, auth_headers, db):
    """Delete collection with items + shares cascades correctly."""
    import uuid as uuid_module

    from sqlmodel import select

    from fourdpocket.models.collection import CollectionItem
    from fourdpocket.models.share import Share, ShareType
    from fourdpocket.models.user import User

    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "Cascade Test"},
        headers=auth_headers,
    )
    collection_id = uuid_module.UUID(coll_resp.json()["id"])

    item_resp = client.post("/api/v1/items", json={"url": "https://cascade.com"}, headers=auth_headers)
    item_id = uuid_module.UUID(item_resp.json()["id"])

    # Get actual user ID from DB
    auth_user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert auth_user is not None

    db.add(CollectionItem(collection_id=collection_id, item_id=item_id))
    share = Share(
        owner_id=auth_user.id,
        share_type=ShareType.collection,
        collection_id=collection_id,
    )
    db.add(share)
    db.commit()

    response = client.delete(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verify collection gone
    get_resp = client.get(f"/api/v1/collections/{collection_id}", headers=auth_headers)
    assert get_resp.status_code == 404
    # Verify collection item link gone (use API)
    list_resp = client.get(f"/api/v1/collections/{collection_id}/items", headers=auth_headers)
    assert list_resp.status_code == 404


def test_add_items_skips_other_user(client, auth_headers, second_user_headers, db):
    """Other user's item is silently skipped."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "Skip Other"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    # Create item as second user
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://other.com"},
        headers=second_user_headers,
    )
    item_id = item_resp.json()["id"]

    response = client.post(
        f"/api/v1/collections/{collection_id}/items",
        json={"item_ids": [item_id]},
        headers=auth_headers,
    )
    assert response.status_code == 201
    # Item from other user is silently skipped
    assert response.json()["added"] == []

    # Verify by listing items - should be empty
    list_resp = client.get(f"/api/v1/collections/{collection_id}/items", headers=auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json() == []


def test_add_items_duplicate_skipped(client, auth_headers):
    """Same item added twice results in no duplicate."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "No Duplicate"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    item_resp = client.post("/api/v1/items", json={"url": "https://dup.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    # Add once
    client.post(
        f"/api/v1/collections/{collection_id}/items",
        json={"item_ids": [item_id]},
        headers=auth_headers,
    )
    # Add same again - should return empty added list
    response = client.post(
        f"/api/v1/collections/{collection_id}/items",
        json={"item_ids": [item_id]},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["added"] == []

    # Verify only one item in collection
    list_resp = client.get(f"/api/v1/collections/{collection_id}/items", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


def test_remove_item_collection_404(client, auth_headers):
    """Remove from non-existent collection returns 404."""
    fake_coll_id = "00000000-0000-0000-0000-000000000004"
    item_resp = client.post("/api/v1/items", json={"url": "https://remove.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    response = client.delete(
        f"/api/v1/collections/{fake_coll_id}/items/{item_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_remove_item_not_in_collection(client, auth_headers):
    """Removing item not in collection returns 404."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "Empty Coll"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    item_resp = client.post("/api/v1/items", json={"url": "https://notincoll.com"}, headers=auth_headers)
    item_id = item_resp.json()["id"]

    response = client.delete(
        f"/api/v1/collections/{collection_id}/items/{item_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_reorder_collection_404(client, auth_headers):
    """Reorder non-existent collection returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000004"
    response = client.put(
        f"/api/v1/collections/{fake_id}/items/reorder",
        json={"items": []},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_smart_collection_items(client, auth_headers, db, monkeypatch):
    """Smart collection returns items from search service."""
    from sqlmodel import select

    from fourdpocket.models.collection import Collection
    from fourdpocket.models.user import User

    # Get auth user
    auth_user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert auth_user is not None

    # Create smart collection via DB (is_smart not in CollectionCreate schema)
    coll = Collection(
        user_id=auth_user.id,
        name="Smart Coll",
        is_smart=True,
        smart_query="python",
    )
    db.add(coll)
    db.commit()
    db.refresh(coll)

    # Mock search service
    class MockResult:
        def to_dict(self):
            return {"id": "mock-id", "title": "Python Article"}

    class MockSearchService:
        def search(self, db, query, user_id, limit=20, offset=0):
            return [MockResult()]

    monkeypatch.setattr("fourdpocket.search.get_search_service", lambda: MockSearchService())

    response = client.get(f"/api/v1/collections/{coll.id}/smart-items", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_smart_collection_non_smart_400(client, auth_headers, db):
    """Non-smart collection returns 400 on smart-items endpoint."""
    from sqlmodel import select

    from fourdpocket.models.collection import Collection
    from fourdpocket.models.user import User

    # Get auth user
    auth_user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert auth_user is not None

    # Create regular (non-smart) collection via DB
    coll = Collection(
        user_id=auth_user.id,
        name="Regular Coll",
        is_smart=False,
    )
    db.add(coll)
    db.commit()
    db.refresh(coll)

    response = client.get(f"/api/v1/collections/{coll.id}/smart-items", headers=auth_headers)
    assert response.status_code == 400


def test_list_collection_items_404(client, auth_headers):
    """List items in non-existent collection returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000004"
    response = client.get(f"/api/v1/collections/{fake_id}/items", headers=auth_headers)
    assert response.status_code == 404


def test_collection_rss(client, auth_headers):
    """GET /collections/{id}/rss returns XML with valid RSS structure."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "RSS Coll"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://example.com", "title": "RSS Item"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    client.post(
        f"/api/v1/collections/{collection_id}/items",
        json={"item_ids": [item_id]},
        headers=auth_headers,
    )

    response = client.get(f"/api/v1/collections/{collection_id}/rss", headers=auth_headers)
    assert response.status_code == 200
    assert "xml" in response.headers.get("content-type", "")
    assert "<title>RSS Coll</title>" in response.text


def test_collection_rss_empty(client, auth_headers):
    """Empty collection returns valid RSS with no items."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "Empty RSS"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    response = client.get(f"/api/v1/collections/{collection_id}/rss", headers=auth_headers)
    assert response.status_code == 200
    assert "xml" in response.headers.get("content-type", "")
    assert "<title>Empty RSS</title>" in response.text


def test_collection_rss_404(client, auth_headers):
    """Non-existent collection RSS returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000004"
    response = client.get(f"/api/v1/collections/{fake_id}/rss", headers=auth_headers)
    assert response.status_code == 404


def test_add_notes_to_collection(client, auth_headers):
    """POST /collections/{id}/notes adds notes to collection."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "Notes Coll"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    note_resp = client.post(
        "/api/v1/notes",
        json={"title": "My Note", "content": "Note content"},
        headers=auth_headers,
    )
    note_id = note_resp.json()["id"]

    response = client.post(
        f"/api/v1/collections/{collection_id}/notes",
        json={"note_ids": [note_id]},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["added"] == [note_id]


def test_add_notes_skip_other_user(client, auth_headers, second_user_headers):
    """Other user's note is silently skipped."""
    # Create collection as first user
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "Skip Notes"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    # Create note as second user
    note_resp = client.post(
        "/api/v1/notes",
        json={"title": "Other Note", "content": "Not yours"},
        headers=second_user_headers,
    )
    note_id = note_resp.json()["id"]

    response = client.post(
        f"/api/v1/collections/{collection_id}/notes",
        json={"note_ids": [note_id]},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["added"] == []


def test_add_notes_duplicate_skipped(client, auth_headers):
    """Same note twice results in no duplicate link."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "Dup Notes"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    note_resp = client.post(
        "/api/v1/notes",
        json={"title": "Dup Note", "content": "Content"},
        headers=auth_headers,
    )
    note_id = note_resp.json()["id"]

    client.post(
        f"/api/v1/collections/{collection_id}/notes",
        json={"note_ids": [note_id]},
        headers=auth_headers,
    )
    response = client.post(
        f"/api/v1/collections/{collection_id}/notes",
        json={"note_ids": [note_id]},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["added"] == []


def test_remove_note_from_collection(client, auth_headers):
    """DELETE /collections/{id}/notes/{nid} removes note from collection."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "RM Notes"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    note_resp = client.post(
        "/api/v1/notes",
        json={"title": "To Remove", "content": "Content"},
        headers=auth_headers,
    )
    note_id = note_resp.json()["id"]

    client.post(
        f"/api/v1/collections/{collection_id}/notes",
        json={"note_ids": [note_id]},
        headers=auth_headers,
    )

    response = client.delete(
        f"/api/v1/collections/{collection_id}/notes/{note_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204


def test_remove_note_not_linked(client, auth_headers):
    """Note not in collection returns 404."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "Not Linked"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    note_resp = client.post(
        "/api/v1/notes",
        json={"title": "Not Linked Note", "content": "Content"},
        headers=auth_headers,
    )
    note_id = note_resp.json()["id"]

    response = client.delete(
        f"/api/v1/collections/{collection_id}/notes/{note_id}",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_list_collection_notes(client, auth_headers):
    """GET /collections/{id}/notes returns notes in collection."""
    coll_resp = client.post(
        "/api/v1/collections",
        json={"name": "List Notes"},
        headers=auth_headers,
    )
    collection_id = coll_resp.json()["id"]

    note1_resp = client.post(
        "/api/v1/notes",
        json={"title": "Note 1", "content": "Content 1"},
        headers=auth_headers,
    )
    note2_resp = client.post(
        "/api/v1/notes",
        json={"title": "Note 2", "content": "Content 2"},
        headers=auth_headers,
    )
    note1_id = note1_resp.json()["id"]
    note2_id = note2_resp.json()["id"]

    client.post(
        f"/api/v1/collections/{collection_id}/notes",
        json={"note_ids": [note1_id, note2_id]},
        headers=auth_headers,
    )

    response = client.get(f"/api/v1/collections/{collection_id}/notes", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_item_collections(client, auth_headers):
    """GET /items/{id}/collections returns collections containing the item."""
    item_resp = client.post(
        "/api/v1/items",
        json={"url": "https://itemcoll.com", "title": "My Item"},
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]

    coll1_resp = client.post(
        "/api/v1/collections",
        json={"name": "Coll 1"},
        headers=auth_headers,
    )
    coll2_resp = client.post(
        "/api/v1/collections",
        json={"name": "Coll 2"},
        headers=auth_headers,
    )
    coll1_id = coll1_resp.json()["id"]
    coll2_id = coll2_resp.json()["id"]

    client.post(
        f"/api/v1/collections/{coll1_id}/items",
        json={"item_ids": [item_id]},
        headers=auth_headers,
    )
    client.post(
        f"/api/v1/collections/{coll2_id}/items",
        json={"item_ids": [item_id]},
        headers=auth_headers,
    )

    response = client.get(f"/api/v1/items/{item_id}/collections", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_item_collections_404(client, auth_headers):
    """Non-existent item returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000001"
    response = client.get(f"/api/v1/items/{fake_id}/collections", headers=auth_headers)
    assert response.status_code == 404
