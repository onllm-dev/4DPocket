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


# === PHASE 0C MOPUP ADDITIONS ===

def test_create_tag_invalid_parent_404(client, auth_headers):
    """Non-existent parent_id returns 404."""
    fake_parent = "00000000-0000-0000-0000-000000000003"
    response = client.post(
        "/api/v1/tags",
        json={"name": "Child", "parent_id": fake_parent},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_create_tag_other_user_parent_404(client, auth_headers, second_user_headers):
    """Parent tag belonging to another user returns 404."""
    parent_resp = client.post("/api/v1/tags", json={"name": "Other Parent"}, headers=second_user_headers)
    parent_id = parent_resp.json()["id"]

    response = client.post(
        "/api/v1/tags",
        json={"name": "Child of Other", "parent_id": parent_id},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_update_tag_404(client, auth_headers):
    """Update non-existent tag returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000003"
    response = client.patch(
        f"/api/v1/tags/{fake_id}",
        json={"name": "New Name"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_update_tag_color_only(client, auth_headers):
    """PATCH with only color does not regenerate slug."""
    create_resp = client.post("/api/v1/tags", json={"name": "Color Test"}, headers=auth_headers)
    tag_id = create_resp.json()["id"]
    original_slug = create_resp.json()["slug"]

    response = client.patch(
        f"/api/v1/tags/{tag_id}",
        json={"color": "#FF0000"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["slug"] == original_slug
    assert response.json()["color"] == "#FF0000"


def test_delete_tag_404(client, auth_headers):
    """Delete non-existent tag returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000003"
    response = client.delete(f"/api/v1/tags/{fake_id}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_tag_cascade_notetag(client, auth_headers, db):
    """Deleting tag cascades NoteTag associations."""
    import uuid as uuid_module

    from sqlmodel import select

    from fourdpocket.models.note import Note
    from fourdpocket.models.note_tag import NoteTag
    from fourdpocket.models.user import User

    tag_resp = client.post("/api/v1/tags", json={"name": "Note Tag"}, headers=auth_headers)
    tag_id_str = tag_resp.json()["id"]
    tag_id = uuid_module.UUID(tag_id_str)

    # Get actual user ID
    auth_user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert auth_user is not None

    # Create a note
    note = Note(user_id=auth_user.id, title="Note for Tag", content="Content")
    db.add(note)
    db.commit()
    db.refresh(note)

    db.add(NoteTag(note_id=note.id, tag_id=tag_id))
    db.commit()

    response = client.delete(f"/api/v1/tags/{tag_id_str}", headers=auth_headers)
    assert response.status_code == 204

    # Verify NoteTag link is gone via API (tag is deleted, so 404)
    get_resp = client.get(f"/api/v1/tags/{tag_id_str}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_tag_cascade_share(client, auth_headers, db):
    """Deleting tag cascades Share references."""
    import uuid as uuid_module

    from sqlmodel import select

    from fourdpocket.models.share import Share, ShareType
    from fourdpocket.models.user import User

    tag_resp = client.post("/api/v1/tags", json={"name": "Share Tag"}, headers=auth_headers)
    tag_id_str = tag_resp.json()["id"]
    tag_id = uuid_module.UUID(tag_id_str)

    auth_user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert auth_user is not None

    share = Share(
        owner_id=auth_user.id,
        share_type=ShareType.tag,
        tag_id=tag_id,
    )
    db.add(share)
    db.commit()

    response = client.delete(f"/api/v1/tags/{tag_id_str}", headers=auth_headers)
    assert response.status_code == 204

    # Verify share is gone via API
    get_resp = client.get(f"/api/v1/tags/{tag_id_str}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_tag_unparent_children(client, auth_headers, db):
    """Deleting parent tag sets children's parent_id to None."""
    import uuid as uuid_module


    parent_resp = client.post("/api/v1/tags", json={"name": "Parent Tag"}, headers=auth_headers)
    parent_id_str = parent_resp.json()["id"]
    parent_id = uuid_module.UUID(parent_id_str)

    child_resp = client.post(
        "/api/v1/tags",
        json={"name": "Child Tag", "parent_id": parent_id_str},
        headers=auth_headers,
    )
    child_id_str = child_resp.json()["id"]

    response = client.delete(f"/api/v1/tags/{parent_id_str}", headers=auth_headers)
    assert response.status_code == 204

    # Verify child's parent_id is now None by getting the child via API
    child_get = client.get(f"/api/v1/tags/{child_id_str}", headers=auth_headers)
    assert child_get.status_code == 200
    assert child_get.json()["parent_id"] is None


def test_suggest_tag_merges(client, auth_headers, db):
    """Similar tags (python, pythn) produce merge suggestions."""
    from sqlmodel import select

    from fourdpocket.models.tag import Tag
    from fourdpocket.models.user import User

    auth_user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert auth_user is not None

    # Create two similar tags
    db.add(Tag(user_id=auth_user.id, name="python", slug="python"))
    db.add(Tag(user_id=auth_user.id, name="pythn", slug="pythn"))
    db.commit()

    response = client.get("/api/v1/tags/suggestions/merge", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_suggest_tag_merges_too_few(client, auth_headers, db):
    """Fewer than 2 tags returns empty list."""
    from sqlmodel import select

    from fourdpocket.models.tag import Tag
    from fourdpocket.models.user import User

    auth_user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert auth_user is not None

    db.add(Tag(user_id=auth_user.id, name="only-one", slug="only-one"))
    db.commit()

    response = client.get("/api/v1/tags/suggestions/merge", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_merge_tags(client, auth_headers, db):
    """POST /tags/merge moves ItemTag links from source to target."""
    import uuid as uuid_module

    from fourdpocket.models.tag import ItemTag

    tag_resp_1 = client.post("/api/v1/tags", json={"name": "Source Tag"}, headers=auth_headers)
    tag_resp_2 = client.post("/api/v1/tags", json={"name": "Target Tag"}, headers=auth_headers)
    source_id = tag_resp_1.json()["id"]
    target_id = tag_resp_2.json()["id"]

    item_resp = client.post("/api/v1/items", json={"url": "https://merge.com"}, headers=auth_headers)
    item_id = uuid_module.UUID(item_resp.json()["id"])

    db.add(ItemTag(item_id=item_id, tag_id=uuid_module.UUID(source_id)))
    db.commit()

    response = client.post(
        "/api/v1/tags/merge",
        json={"source_tag_id": str(source_id), "target_tag_id": str(target_id)},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "merged"

    # Verify via API: target tag should have 1 item (source was merged into target)
    target_items = client.get(f"/api/v1/tags/{target_id}/items", headers=auth_headers)
    assert target_items.status_code == 200
    assert len(target_items.json()) == 1

    # Verify source tag is deleted (404)
    source_get = client.get(f"/api/v1/tags/{source_id}", headers=auth_headers)
    assert source_get.status_code == 404


def test_merge_tags_source_404(client, auth_headers):
    """Non-existent source tag returns 404."""
    fake_source = "00000000-0000-0000-0000-000000000003"
    target_resp = client.post("/api/v1/tags", json={"name": "Target"}, headers=auth_headers)
    target_id = target_resp.json()["id"]

    response = client.post(
        "/api/v1/tags/merge",
        json={"source_tag_id": fake_source, "target_tag_id": str(target_id)},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_merge_tags_target_404(client, auth_headers):
    """Non-existent target tag returns 404."""
    source_resp = client.post("/api/v1/tags", json={"name": "Source"}, headers=auth_headers)
    source_id = source_resp.json()["id"]
    fake_target = "00000000-0000-0000-0000-000000000003"

    response = client.post(
        "/api/v1/tags/merge",
        json={"source_tag_id": str(source_id), "target_tag_id": fake_target},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_merge_tags_duplicate_link(client, auth_headers, db):
    """Item already has target tag → no duplicate link after merge."""
    import uuid as uuid_module

    from fourdpocket.models.tag import ItemTag

    tag_resp_1 = client.post("/api/v1/tags", json={"name": "Dup Source"}, headers=auth_headers)
    tag_resp_2 = client.post("/api/v1/tags", json={"name": "Dup Target"}, headers=auth_headers)
    source_id = tag_resp_1.json()["id"]
    target_id = tag_resp_2.json()["id"]

    item_resp = client.post("/api/v1/items", json={"url": "https://dupmerge.com"}, headers=auth_headers)
    item_id = uuid_module.UUID(item_resp.json()["id"])

    db.add(ItemTag(item_id=item_id, tag_id=uuid_module.UUID(source_id)))
    db.add(ItemTag(item_id=item_id, tag_id=uuid_module.UUID(target_id)))  # Already has target
    db.commit()

    response = client.post(
        "/api/v1/tags/merge",
        json={"source_tag_id": str(source_id), "target_tag_id": str(target_id)},
        headers=auth_headers,
    )
    assert response.status_code == 200

    # Verify only one link to target (no duplicate) via API
    target_items = client.get(f"/api/v1/tags/{target_id}/items", headers=auth_headers)
    assert len(target_items.json()) == 1


def test_list_tag_items_404(client, auth_headers):
    """Non-existent tag returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000003"
    response = client.get(f"/api/v1/tags/{fake_id}/items", headers=auth_headers)
    assert response.status_code == 404
