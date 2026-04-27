"""Security-headers middleware.

Sets hardened HTTP response headers on every request.  CSP is skipped on
FastAPI's built-in documentation routes (/docs, /redoc, /openapi.json) because
Swagger UI and ReDoc load resources from CDNs and require 'unsafe-inline'.

HSTS is only added when server.secure_cookies is True — that flag signals that
the app is running behind HTTPS (reverse proxy or direct TLS).
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Paths where we skip Content-Security-Policy so Swagger/ReDoc work correctly.
_CSP_SKIP_PATHS = frozenset(["/docs", "/redoc", "/openapi.json"])

# CSP suitable for a same-origin SPA that bundles its own assets.
_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob: https:; "
    "connect-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every HTTP response."""

    def __init__(self, app, secure: bool = False):
        super().__init__(app)
        self._secure = secure

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"

        if self._secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Skip CSP on API documentation routes.
        if request.url.path not in _CSP_SKIP_PATHS:
            response.headers["Content-Security-Policy"] = _CSP

        return response
