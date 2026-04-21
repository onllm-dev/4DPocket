"""Regression tests for PAT write enforcement."""

import uuid

from sqlmodel import select

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
