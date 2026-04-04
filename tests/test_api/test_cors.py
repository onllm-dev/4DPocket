"""Tests for CORS middleware, including browser extension origins."""


def test_cors_allows_chrome_extension_origin(client):
    """Should return CORS headers for chrome-extension:// origins."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnop",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "chrome-extension://abcdefghijklmnop"


def test_cors_allows_moz_extension_origin(client):
    """Should return CORS headers for moz-extension:// origins."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "moz-extension://some-uuid-here",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "moz-extension://some-uuid-here"


def test_cors_allows_configured_origin(client):
    """Should still allow configured origins like localhost."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_blocks_unknown_origin(client):
    """Should not return CORS headers for unknown origins."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None
