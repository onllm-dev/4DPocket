"""Tests: PATs authenticate existing endpoints, roles and flags enforced."""


def _mint(client, headers, **overrides):
    payload = {"name": "t", "role": "viewer", "all_collections": True}
    payload.update(overrides)
    res = client.post("/api/v1/auth/tokens", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["token"]


def _pat_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_pat_authenticates_me_endpoint(client, auth_headers):
    token = _mint(client, auth_headers)
    res = client.get("/api/v1/auth/me", headers=_pat_headers(token))
    assert res.status_code == 200
    assert res.json()["email"] == "test@example.com"


def test_pat_lists_items(client, auth_headers):
    token = _mint(client, auth_headers)
    # Create an item via JWT
    client.post(
        "/api/v1/items",
        json={
            "title": "Hello",
            "content": "world",
            "item_type": "note",
            "source_platform": "generic",
        },
        headers=auth_headers,
    )
    # Read via PAT
    res = client.get("/api/v1/items", headers=_pat_headers(token))
    assert res.status_code == 200
    assert any(i["title"] == "Hello" for i in res.json())


def test_invalid_pat_rejected(client):
    res = client.get(
        "/api/v1/auth/me", headers=_pat_headers("fdp_pat_bogus_nope")
    )
    assert res.status_code == 401


def test_malformed_pat_rejected(client):
    res = client.get("/api/v1/auth/me", headers=_pat_headers("fdp_pat_nodashes"))
    assert res.status_code == 401


def test_revoked_pat_rejected(client, auth_headers):
    res = client.post(
        "/api/v1/auth/tokens",
        json={"name": "t", "role": "viewer", "all_collections": True},
        headers=auth_headers,
    )
    data = res.json()
    token_plain = data["token"]
    token_id = data["id"]

    # Token works first
    r1 = client.get("/api/v1/auth/me", headers=_pat_headers(token_plain))
    assert r1.status_code == 200

    # Revoke
    client.delete(f"/api/v1/auth/tokens/{token_id}", headers=auth_headers)

    # Now rejected
    r2 = client.get("/api/v1/auth/me", headers=_pat_headers(token_plain))
    assert r2.status_code == 401


def test_admin_endpoint_rejects_non_admin_scope_pat(client, auth_headers):
    # auth_headers is the admin (first registered user).
    # PAT without admin_scope must be blocked by our guard even though the user is admin.
    token = _mint(client, auth_headers, admin_scope=False)
    res = client.get("/api/v1/admin/users", headers=_pat_headers(token))
    assert res.status_code == 403


def test_admin_endpoint_allows_admin_scope_pat(client, auth_headers):
    token = _mint(client, auth_headers, admin_scope=True)
    res = client.get("/api/v1/admin/users", headers=_pat_headers(token))
    assert res.status_code == 200


def test_pat_after_user_disabled_rejected(client, auth_headers, db):
    from sqlmodel import select

    from fourdpocket.models.user import User

    token = _mint(client, auth_headers)

    # Disable the user directly in the DB
    user = db.exec(select(User).where(User.email == "test@example.com")).first()
    user.is_active = False
    db.add(user)
    db.commit()

    res = client.get("/api/v1/auth/me", headers=_pat_headers(token))
    assert res.status_code in (401, 403)
