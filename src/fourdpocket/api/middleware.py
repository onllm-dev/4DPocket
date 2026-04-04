"""API middleware - rate limiting and request ID."""

import time
import uuid
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


_MAX_TRACKED_IPS = 10000


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding window rate limiter."""

    def __init__(self, app, max_requests: int = 1000, window_seconds: int = 60, trust_proxy: bool = False):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.trust_proxy = trust_proxy
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP. Only trusts X-Forwarded-For when trust_proxy is True."""
        if self.trust_proxy:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean old entries for this IP
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > cutoff
        ]

        # Evict stale IPs to prevent unbounded memory growth
        if len(self._requests) > _MAX_TRACKED_IPS:
            stale = [k for k, v in self._requests.items() if not v]
            for k in stale:
                del self._requests[k]

        if len(self._requests[client_ip]) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
            )

        self._requests[client_ip].append(now)
        response = await call_next(request)
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add X-Request-ID header to all responses."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
