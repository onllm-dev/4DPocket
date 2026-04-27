"""Tests for SecurityHeadersMiddleware.

Covers:
  - Core security headers always present.
  - CSP present on normal routes.
  - CSP absent on /docs, /redoc, /openapi.json.
  - HSTS absent when secure=False (default).
  - HSTS present when secure=True.
"""

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from fourdpocket.middleware.security_headers import SecurityHeadersMiddleware


def _make_app(secure: bool = False):
    async def handler(request: Request):
        return PlainTextResponse("ok")

    app = Starlette(
        routes=[
            Route("/api/data", handler),
            Route("/docs", handler),
            Route("/redoc", handler),
            Route("/openapi.json", handler),
        ]
    )
    app.add_middleware(SecurityHeadersMiddleware, secure=secure)
    return app


class TestSecurityHeadersMiddleware:
    def test_core_headers_always_present(self):
        """X-Content-Type-Options, X-Frame-Options, Referrer-Policy are set."""
        client = TestClient(_make_app())
        response = client.get("/api/data")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_csp_present_on_normal_route(self):
        """Content-Security-Policy is set on non-docs routes."""
        client = TestClient(_make_app())
        response = client.get("/api/data")
        assert "content-security-policy" in response.headers
        csp = response.headers["content-security-policy"]
        assert "default-src 'self'" in csp

    def test_csp_skipped_on_docs(self):
        """CSP is NOT set on /docs to allow Swagger UI to function."""
        client = TestClient(_make_app())
        response = client.get("/docs")
        assert "content-security-policy" not in response.headers

    def test_csp_skipped_on_redoc(self):
        """CSP is NOT set on /redoc."""
        client = TestClient(_make_app())
        response = client.get("/redoc")
        assert "content-security-policy" not in response.headers

    def test_csp_skipped_on_openapi_json(self):
        """CSP is NOT set on /openapi.json."""
        client = TestClient(_make_app())
        response = client.get("/openapi.json")
        assert "content-security-policy" not in response.headers

    def test_hsts_absent_when_not_secure(self):
        """Strict-Transport-Security is omitted when secure=False."""
        client = TestClient(_make_app(secure=False))
        response = client.get("/api/data")
        assert "strict-transport-security" not in response.headers

    def test_hsts_present_when_secure(self):
        """Strict-Transport-Security is set when secure=True."""
        client = TestClient(_make_app(secure=True))
        response = client.get("/api/data")
        hsts = response.headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
