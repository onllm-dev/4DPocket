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


def test_pats_invalidated_after_password_change(client, auth_headers, db):
    """PATs must be deleted when the user changes their password.

    Regression test for: PATs not invalidated on password change.
    Root cause: change_password only updated password_hash, left ApiToken rows alive.
    Fixed in: src/fourdpocket/api/auth.py change_password
    """
    from sqlmodel import select

    from fourdpocket.models.api_token import ApiToken
    from fourdpocket.models.user import User

    # Create a PAT
    res = _create_token(client, auth_headers, name="should-be-killed")
    assert res.status_code == 201
    raw_token = res.json()["token"]

    # Verify it works before password change
    pre = client.get("/api/v1/items", headers={"Authorization": f"Bearer {raw_token}"})
    assert pre.status_code == 200

    # Change password
    pw_resp = client.patch(
        "/api/v1/auth/password",
        json={"current_password": "TestPass123!", "new_password": "NewPass456!"},
        headers=auth_headers,
    )
    assert pw_resp.status_code == 204

    # PAT must no longer work
    post = client.get("/api/v1/items", headers={"Authorization": f"Bearer {raw_token}"})
    assert post.status_code == 401

    # DB must have zero tokens for this user
    user = db.exec(select(User).where(User.email == "test@example.com")).first()
    remaining = db.exec(select(ApiToken).where(ApiToken.user_id == user.id)).all()
    assert remaining == []


def test_dummy_timing_compare_uses_input(monkeypatch):
    """Constant-time dummy compare must hash the actual input, not a fixed constant.

    Regression test for: compare_digest(_DUMMY_HASH, _DUMMY_HASH) leaks nothing
    about input — replaced with hash(input[:50]) vs _DUMMY_HASH.
    Fixed in: src/fourdpocket/api/api_token_utils.py resolve_token
    """
    import hmac as _hmac

    import fourdpocket.api.api_token_utils as utils

    calls = []
    original = _hmac.compare_digest

    def _spy(a, b):
        calls.append((a, b))
        return original(a, b)

    monkeypatch.setattr(_hmac, "compare_digest", _spy)

    # Pass a totally invalid token (no fdp_pat_ prefix) — must fall through to dummy branch
    from unittest.mock import MagicMock
    db = MagicMock()
    utils.resolve_token(db, "not_a_valid_token_at_all")

    assert len(calls) == 1
    # a must NOT equal b (we're comparing a real hash against _DUMMY_HASH)
    a, b = calls[0]
    assert b == utils._DUMMY_HASH
    assert a != b  # hash of input[:50] won't match "0"*64


def test_generated_tokens_always_parse():
    """Regression: prior urlsafe-base64 prefixes could contain ``_``, which
    collided with the ``fdp_pat_<prefix>_<secret>`` separator and made
    ~17% of tokens fail to resolve. Hex prefix must round-trip every time.
    """
    from fourdpocket.api.api_token_utils import (
        TOKEN_PREFIX,
        _parse_prefix,
        generate_token,
    )

    for _ in range(500):
        gen = generate_token()
        assert gen.plaintext.startswith(TOKEN_PREFIX)
        assert "_" not in gen.prefix, f"prefix must not contain separator: {gen.prefix!r}"
        parsed = _parse_prefix(gen.plaintext)
        assert parsed == gen.prefix, (
            f"round-trip failed: generated prefix={gen.prefix!r} parsed={parsed!r}"
        )
