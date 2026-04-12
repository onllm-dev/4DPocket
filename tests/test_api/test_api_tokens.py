"""Personal Access Token CRUD tests."""

import uuid


def _create_token(client, auth_headers, **overrides):
    payload = {"name": "test-token", "role": "viewer", "all_collections": True}
    payload.update(overrides)
    return client.post("/api/v1/auth/tokens", json=payload, headers=auth_headers)


def test_create_token_returns_plaintext_once(client, auth_headers):
    res = _create_token(client, auth_headers, name="claude-desktop")
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "claude-desktop"
    assert data["role"] == "viewer"
    assert data["token"].startswith("fdp_pat_")
    assert len(data["prefix"]) > 0
    assert data["revoked_at"] is None
    assert data["last_used_at"] is None

    # List response never contains plaintext
    listing = client.get("/api/v1/auth/tokens", headers=auth_headers).json()
    assert len(listing) == 1
    assert "token" not in listing[0]
    assert listing[0]["prefix"] == data["prefix"]


def test_list_tokens_scoped_to_user(client, auth_headers, second_user_headers):
    _create_token(client, auth_headers, name="user-a-token")
    _create_token(client, second_user_headers, name="user-b-token")

    a_list = client.get("/api/v1/auth/tokens", headers=auth_headers).json()
    b_list = client.get("/api/v1/auth/tokens", headers=second_user_headers).json()

    assert {t["name"] for t in a_list} == {"user-a-token"}
    assert {t["name"] for t in b_list} == {"user-b-token"}


def test_revoke_token(client, auth_headers):
    token = _create_token(client, auth_headers).json()
    token_id = token["id"]

    res = client.delete(f"/api/v1/auth/tokens/{token_id}", headers=auth_headers)
    assert res.status_code == 204

    listing = client.get("/api/v1/auth/tokens", headers=auth_headers).json()
    assert listing[0]["revoked_at"] is not None


def test_revoke_other_users_token_forbidden(client, auth_headers, second_user_headers):
    token = _create_token(client, auth_headers).json()
    token_id = token["id"]
    res = client.delete(
        f"/api/v1/auth/tokens/{token_id}", headers=second_user_headers
    )
    assert res.status_code == 404


def test_revoke_all_tokens(client, auth_headers):
    _create_token(client, auth_headers, name="t1")
    _create_token(client, auth_headers, name="t2")
    _create_token(client, auth_headers, name="t3")

    res = client.post("/api/v1/auth/tokens/revoke-all", headers=auth_headers)
    assert res.status_code == 204

    listing = client.get("/api/v1/auth/tokens", headers=auth_headers).json()
    assert len(listing) == 3
    assert all(t["revoked_at"] is not None for t in listing)


def test_non_admin_cannot_create_admin_scope_token(
    client, auth_headers, second_user_headers
):
    # Requesting auth_headers first guarantees it registered first and is admin;
    # second_user_headers is therefore a non-admin user.
    _ = auth_headers  # noqa: F841 — order matters: must register admin first
    res = _create_token(
        client, second_user_headers, name="bad-admin", admin_scope=True
    )
    assert res.status_code == 403


def test_admin_can_create_admin_scope_token(client, auth_headers):
    # auth_headers registers the FIRST user, which becomes admin.
    res = _create_token(client, auth_headers, name="admin-token", admin_scope=True)
    assert res.status_code == 201
    assert res.json()["admin_scope"] is True


def test_collection_scoped_token_requires_collection_ids(client, auth_headers):
    res = _create_token(client, auth_headers, all_collections=False, collection_ids=[])
    assert res.status_code == 400


def test_collection_scoped_token_rejects_foreign_collections(
    client, auth_headers, second_user_headers
):
    coll_a = client.post(
        "/api/v1/collections", json={"name": "A"}, headers=auth_headers
    ).json()
    res = _create_token(
        client,
        second_user_headers,
        all_collections=False,
        collection_ids=[coll_a["id"]],
    )
    assert res.status_code == 400


def test_collection_scoped_token_stores_collection_ids(client, auth_headers):
    coll = client.post(
        "/api/v1/collections", json={"name": "Research"}, headers=auth_headers
    ).json()
    res = _create_token(
        client,
        auth_headers,
        name="research-only",
        all_collections=False,
        collection_ids=[coll["id"]],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["all_collections"] is False
    assert uuid.UUID(coll["id"]) in [uuid.UUID(c) for c in data["collection_ids"]]


def test_invalid_expiry_rejected(client, auth_headers):
    res = _create_token(client, auth_headers, expires_in_days=5)
    assert res.status_code == 422


def test_editor_role_stored(client, auth_headers):
    res = _create_token(client, auth_headers, name="editor-token", role="editor")
    assert res.status_code == 201
    assert res.json()["role"] == "editor"


def test_allow_deletion_flag_stored(client, auth_headers):
    res = _create_token(
        client, auth_headers, name="destroyer", role="editor", allow_deletion=True
    )
    assert res.status_code == 201
    assert res.json()["allow_deletion"] is True
