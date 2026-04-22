"""Regression tests for PAT write enforcement."""

import uuid

from sqlmodel import select

from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.user import User
from tests.factories import make_item, make_pat


def _current_user(db):
    user = db.exec(select(User).where(User.email == "test@example.com")).first()
    assert user is not None
    return user


def _pat_headers(db, **kwargs):
    user = _current_user(db)
    _, raw_token = make_pat(db, user.id, **kwargs)
    return {"Authorization": f"Bearer {raw_token}"}


def test_viewer_pat_can_read_items(client, auth_headers, db):
    user = _current_user(db)
    make_item(db, user.id, title="Viewer-readable item", item_type="note")

    response = client.get("/api/v1/items", headers=_pat_headers(db, role="viewer"))

    assert response.status_code == 200
    assert any(item["title"] == "Viewer-readable item" for item in response.json())


def test_viewer_pat_cannot_create_item(client, auth_headers, db):
    response = client.post(
        "/api/v1/items",
        json={"title": "Blocked", "content": "viewer PAT", "item_type": "note"},
        headers=_pat_headers(db, role="viewer"),
    )

    assert response.status_code == 403


def test_editor_pat_can_create_item(client, auth_headers, db):
    response = client.post(
        "/api/v1/items",
        json={"title": "Allowed", "content": "editor PAT", "item_type": "note"},
        headers=_pat_headers(db, role="editor"),
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Allowed"


def test_editor_pat_without_allow_deletion_cannot_delete_item(client, auth_headers, db):
    user = _current_user(db)
    item = make_item(db, user.id, title="Delete blocked", item_type="note")

    response = client.delete(
        f"/api/v1/items/{item.id}",
        headers=_pat_headers(db, role="editor", allow_deletion=False),
    )

    assert response.status_code == 403


def test_editor_pat_without_allow_deletion_cannot_bulk_delete(
    client, auth_headers, db
):
    user = _current_user(db)
    item = make_item(db, user.id, title="Bulk delete blocked", item_type="note")

    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "delete", "item_ids": [str(item.id)]},
        headers=_pat_headers(db, role="editor", allow_deletion=False),
    )

    assert response.status_code == 403


def test_pat_cannot_mint_additional_tokens(client, auth_headers, db):
    response = client.post(
        "/api/v1/auth/tokens",
        json={"name": "nested", "role": "editor", "all_collections": True},
        headers=_pat_headers(db, role="editor"),
    )

    assert response.status_code == 403


def test_pat_cannot_patch_own_profile(client, auth_headers, db):
    response = client.patch(
        "/api/v1/auth/me",
        json={"display_name": "Blocked via PAT"},
        headers=_pat_headers(db, role="editor"),
    )

    assert response.status_code == 403


def _make_collection_scoped_pat(db, user_id, collection_id):
    """Helper: PAT scoped to one collection only (all_collections=False, include_uncollected=False)."""
    from fourdpocket.models.api_token import ApiTokenCollection

    pat, raw = make_pat(db, user_id, role="editor", all_collections=False, allow_deletion=True)
    # Explicitly disable include_uncollected so items outside the collection are blocked
    pat.include_uncollected = False
    db.add(pat)
    db.commit()
    db.refresh(pat)
    link = ApiTokenCollection(token_id=pat.id, collection_id=collection_id)
    db.add(link)
    db.commit()
    return pat, raw


# --- Bug 1: PAT collection ACL bypass ---

def test_collection_scoped_pat_cannot_list_items_outside_collection(client, auth_headers, db):
    """PAT with all_collections=False must not expose items outside its allowed collections.

    Regression test for: PAT collection ACL bypass in list_items.
    Root cause: list_items only filtered by user_id, ignoring PAT collection restrictions.
    Fixed in: src/fourdpocket/api/items.py list_items
    """
    user = _current_user(db)

    # Create a collection scoped to the PAT
    allowed_col = Collection(user_id=user.id, name="Allowed Col")
    db.add(allowed_col)
    db.commit()
    db.refresh(allowed_col)

    # Item IN the allowed collection
    in_item = make_item(db, user.id, url="https://in-collection.com", title="In Collection", item_type="note")
    db.add(CollectionItem(collection_id=allowed_col.id, item_id=in_item.id))
    db.commit()

    # Item NOT in any collection
    make_item(db, user.id, url="https://out-collection.com", title="Out Collection", item_type="note")

    _, raw = _make_collection_scoped_pat(db, user.id, allowed_col.id)
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.get("/api/v1/items", headers=headers)
    assert response.status_code == 200
    titles = {i["title"] for i in response.json()}
    assert "In Collection" in titles
    assert "Out Collection" not in titles


def test_collection_scoped_pat_cannot_get_item_outside_collection(client, auth_headers, db):
    """PAT with all_collections=False must return 404 for items not in its collections.

    Regression test for: PAT collection ACL bypass in get_item.
    Root cause: get_item only checked user_id ownership.
    Fixed in: src/fourdpocket/api/items.py get_item
    """
    user = _current_user(db)

    allowed_col = Collection(user_id=user.id, name="Scoped Col")
    db.add(allowed_col)
    db.commit()
    db.refresh(allowed_col)

    # Item NOT in the allowed collection
    out_item = make_item(db, user.id, url="https://outside.com", title="Outside", item_type="note")

    _, raw = _make_collection_scoped_pat(db, user.id, allowed_col.id)
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.get(f"/api/v1/items/{out_item.id}", headers=headers)
    assert response.status_code == 404


def test_collection_scoped_pat_can_get_item_inside_collection(client, auth_headers, db):
    """PAT with all_collections=False can access items inside its allowed collection."""
    user = _current_user(db)

    allowed_col = Collection(user_id=user.id, name="Allowed Col 2")
    db.add(allowed_col)
    db.commit()
    db.refresh(allowed_col)

    in_item = make_item(db, user.id, url="https://inside.com", title="Inside", item_type="note")
    db.add(CollectionItem(collection_id=allowed_col.id, item_id=in_item.id))
    db.commit()

    _, raw = _make_collection_scoped_pat(db, user.id, allowed_col.id)
    headers = {"Authorization": f"Bearer {raw}"}

    response = client.get(f"/api/v1/items/{in_item.id}", headers=headers)
    assert response.status_code == 200


# --- Bug 3: update_item doesn't re-index ---

def test_update_item_does_not_raise_on_search_index_failure(client, auth_headers, db):
    """update_item must succeed even when search indexing fails.

    Regression test for: update_item doesn't re-index after commit.
    Root cause: no index_item call after db.refresh(item).
    Fixed in: src/fourdpocket/api/items.py update_item
    """
    user = _current_user(db)
    item = make_item(db, user.id, title="Before Update", item_type="note")

    response = client.patch(
        f"/api/v1/items/{item.id}",
        json={"title": "After Update"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "After Update"


# --- Bug 4: bulk_action tag branch silent-skips invalid tags ---

def test_bulk_tag_with_invalid_tag_id_returns_404(client, auth_headers, db):
    """bulk_action tag with a tag_id not owned by user must return 404.

    Regression test for: bulk tag branch silently skips unowned tag_id.
    Root cause: ownership check inside per-item loop allowed silent skip.
    Fixed in: src/fourdpocket/api/items.py bulk_action
    """
    user = _current_user(db)
    item = make_item(db, user.id, title="Item to tag", item_type="note")
    nonexistent_tag_id = str(uuid.uuid4())

    response = client.post(
        "/api/v1/items/bulk",
        json={"action": "tag", "item_ids": [str(item.id)], "tag_id": nonexistent_tag_id},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_admin_scope_viewer_pat_can_read_admin_but_not_mutate(
    client, auth_headers, db
):
    headers = _pat_headers(db, role="viewer", admin_scope=True)

    read_response = client.get("/api/v1/admin/users", headers=headers)
    assert read_response.status_code == 200

    mutate_response = client.patch(
        "/api/v1/admin/settings",
        json={"instance_name": f"blocked-{uuid.uuid4()}"},
        headers=headers,
    )
    assert mutate_response.status_code == 403
