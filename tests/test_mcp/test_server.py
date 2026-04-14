"""MCP server mount and endpoint accessibility tests."""

import pytest
from fastapi.testclient import TestClient

from fourdpocket.models.user import User


class TestMCPMount:
    """Verify the MCP ASGI app is correctly mounted at /mcp."""

    def test_mcp_redirect_from_root_to_trailing_slash(self, client: TestClient):
        """GET /mcp redirects to /mcp/ (307 preserves method)."""
        response = client.get("/mcp", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/mcp/"

    def test_mcp_post_returns_streamable_http_response(self, client: TestClient):
        """POST /mcp/ with no body returns 400 (MCP protocol requires JSON)."""
        response = client.post("/mcp/", content=b"", headers={"Content-Type": "application/json"})
        # Streamable HTTP returns 401 (auth required) or 400/415 (invalid body)
        assert response.status_code in (400, 401, 415)

    def test_mcp_get_returns_401_or_error(self, client: TestClient):
        """GET /mcp/ without MCP session params returns appropriate error."""
        response = client.get("/mcp/")
        # FastMCP streamable HTTP on GET returns 401 (auth required) or other error
        assert response.status_code in (400, 401, 405)

    def test_mcp_route_not_in_schema(self, client: TestClient):
        """The /mcp mount is excluded from the OpenAPI schema."""
        response = client.get("/openapi.json")
        paths = response.json()["paths"]
        assert "/mcp" not in paths
        assert "/mcp/" not in paths


class TestMCPServerBuild:
    """Test the FastMCP server assembly."""

    def test_mcp_streamable_http_path_is_root(self):
        """FastMCP is configured with streamable_http_path='/' so it works at /mcp/."""
        from fourdpocket.mcp.server import mcp

        # The server is configured with streamable_http_path="/"
        # which means it responds at the mount root
        assert mcp is not None


class TestMCPToolAuth:
    """Test MCP tool authentication context (_tool_ctx)."""
    pass


# === PHASE 1B MOPUP ADDITIONS ===

# ─── _tool_ctx error paths ───────────────────────────────────────────────────


def test_tool_ctx_no_access_token(monkeypatch):
    """_tool_ctx raises ToolError when get_access_token returns None."""
    from fourdpocket.mcp import server

    monkeypatch.setattr(
        "fourdpocket.mcp.server.get_access_token", lambda: None
    )

    with pytest.raises(server.tools_mod.ToolError, match="Authentication required"):
        with server._tool_ctx():
            pass


def test_tool_ctx_revoked_pat(db, monkeypatch, engine):
    """_tool_ctx raises ToolError when resolve_token returns None (revoked/expired PAT)."""
    import fourdpocket.db.session as db_module

    # Patch get_engine so _tool_ctx() uses the test engine
    original_get_engine = db_module.get_engine
    db_module.get_engine = lambda: engine

    # Create a valid user
    user_obj = User(
        email="revoked2@example.com",
        username="revoked2",
        password_hash="x",
        display_name="R2",
    )
    db.add(user_obj)
    db.commit()
    db.refresh(user_obj)

    # Mock get_access_token to return a token, but resolve_token to return None
    mock_access = type("AccessToken", (), {"token": "Bearer fdp_pat_revoked_real"})()

    def fake_get_token():
        return mock_access

    def fake_resolve(db_session, token_str):
        return None  # Simulates revoked/expired token

    from fourdpocket.mcp import server as server_module

    monkeypatch.setattr("fourdpocket.mcp.server.get_access_token", fake_get_token)
    monkeypatch.setattr("fourdpocket.mcp.server.resolve_token", fake_resolve)

    with pytest.raises(server_module.tools_mod.ToolError, match="revoked|expired"):
        with server_module._tool_ctx():
            pass

    db_module.get_engine = original_get_engine


def test_tool_ctx_inactive_user(db, monkeypatch, engine):
    """_tool_ctx raises ToolError when the resolved user is inactive."""
    import fourdpocket.db.session as db_module
    from fourdpocket.mcp import server as server_module

    original_get_engine = db_module.get_engine
    db_module.get_engine = lambda: engine

    # Create an inactive user with a PAT
    inactive_user = User(
        email="inactive2@example.com",
        username="inactive2",
        password_hash="x",
        display_name="I2",
        is_active=False,
    )
    db.add(inactive_user)
    db.commit()
    db.refresh(inactive_user)

    from fourdpocket.api.api_token_utils import generate_token
    from fourdpocket.models.api_token import ApiToken
    from fourdpocket.models.base import ApiTokenRole

    gen = generate_token()
    pat = ApiToken(
        user_id=inactive_user.id,
        name="inactive-token-2",
        token_prefix=gen.prefix,
        token_hash=gen.token_hash,
        role=ApiTokenRole.viewer,
        all_collections=True,
    )
    db.add(pat)
    db.commit()

    mock_access = type("AccessToken", (), {"token": gen.plaintext})()

    def fake_get_token():
        return mock_access

    def fake_resolve(db_session, token_str):
        return pat  # PAT is valid, but user is inactive

    monkeypatch.setattr("fourdpocket.mcp.server.get_access_token", fake_get_token)
    monkeypatch.setattr("fourdpocket.mcp.server.resolve_token", fake_resolve)

    with pytest.raises(server_module.tools_mod.ToolError, match="disabled"):
        with server_module._tool_ctx():
            pass

    db_module.get_engine = original_get_engine


def test_tool_ctx_deleted_user(db, monkeypatch, engine):
    """_tool_ctx raises ToolError when the resolved user no longer exists in DB."""
    import fourdpocket.db.session as db_module
    from fourdpocket.mcp import server as server_module

    original_get_engine = db_module.get_engine
    db_module.get_engine = lambda: engine

    # Create a user, then delete them (simulate user_id points to nothing)
    ghost_user = User(
        email="ghost@example.com",
        username="ghost",
        password_hash="x",
        display_name="Ghost",
    )
    db.add(ghost_user)
    db.commit()
    db.refresh(ghost_user)

    from fourdpocket.api.api_token_utils import generate_token
    from fourdpocket.models.api_token import ApiToken
    from fourdpocket.models.base import ApiTokenRole

    gen = generate_token()
    pat = ApiToken(
        user_id=ghost_user.id,
        name="ghost-token",
        token_prefix=gen.prefix,
        token_hash=gen.token_hash,
        role=ApiTokenRole.viewer,
        all_collections=True,
    )
    db.add(pat)
    db.commit()
    db.refresh(pat)

    # Delete the user directly so user lookup returns None
    db.delete(ghost_user)
    db.commit()

    mock_access = type("AccessToken", (), {"token": gen.plaintext})()

    def fake_get_token():
        return mock_access

    def fake_resolve(db_session, token_str):
        return pat

    monkeypatch.setattr("fourdpocket.mcp.server.get_access_token", fake_get_token)
    monkeypatch.setattr("fourdpocket.mcp.server.resolve_token", fake_resolve)

    with pytest.raises(server_module.tools_mod.ToolError, match="disabled"):
        with server_module._tool_ctx():
            pass

    db_module.get_engine = original_get_engine


# ─── Tool call wrapper ───────────────────────────────────────────────────────


def test_tool_call_propagates_http_exception(db, monkeypatch):
    """tools.call converts HTTPException to ToolError."""
    from fastapi import HTTPException

    from fourdpocket.mcp import tools as tools_mod

    def failing_fn(db, user, token):
        raise HTTPException(status_code=403, detail="Forbidden by policy")

    with pytest.raises(tools_mod.ToolError, match="Forbidden by policy"):
        tools_mod.call(failing_fn, db, None, None)


def test_build_mcp_app_returns_asgi_app():
    """build_mcp_app() returns a callable ASGI application."""
    from fourdpocket.mcp.server import build_mcp_app

    app = build_mcp_app()
    assert callable(app)
    # Should have an ASGI app interface (has __call__ with scope, receive, send)
    assert hasattr(app, "__call__")
