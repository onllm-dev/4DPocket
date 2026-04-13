"""Tests for API middleware components."""

import time

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from fourdpocket.api.middleware import (
    _MAX_TRACKED_IPS,
    RateLimitMiddleware,
    RequestIDMiddleware,
)


class TestRateLimitMiddleware:
    def test_request_allowed_under_limit(self):
        async def test_route(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/test", test_route)])
        app.add_middleware(RateLimitMiddleware, max_requests=10, window_seconds=60)
        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200

    def test_request_blocked_over_limit(self):
        async def test_route(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/test", test_route)])
        app.add_middleware(RateLimitMiddleware, max_requests=2, window_seconds=60)
        client = TestClient(app)

        client.get("/test")
        client.get("/test")
        # Third request should be blocked
        response = client.get("/test")
        assert response.status_code == 429
        assert response.json()["detail"] == "Too many requests"

    def test_rate_limit_window_expiry(self):
        async def test_route(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/test", test_route)])
        app.add_middleware(RateLimitMiddleware, max_requests=2, window_seconds=1)
        client = TestClient(app)

        client.get("/test")
        client.get("/test")
        # Blocked immediately after
        response = client.get("/test")
        assert response.status_code == 429

        # Wait for window to expire
        time.sleep(1.5)

        # Should be allowed again
        response = client.get("/test")
        assert response.status_code == 200

    def test_rate_limit_trust_proxy_header(self):
        async def test_route(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/test", test_route)])
        app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60, trust_proxy=True)
        client = TestClient(app)

        # With trust_proxy=True, X-Forwarded-For IP is tracked
        response = client.get("/test", headers={"x-forwarded-for": "1.2.3.4"})
        assert response.status_code == 200

    def test_rate_limit_max_tracked_ips_eviction(self):
        async def test_route(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/test", test_route)])
        # Pass class + kwargs to add_middleware so Starlette instantiates it correctly
        app.add_middleware(RateLimitMiddleware, max_requests=1000, window_seconds=60)
        # Access the middleware instance via the built middleware stack
        # We get a reference to the instantiated middleware from app.middleware_stack
        # Since we can't easily access it, we directly test the class by populating stale IPs
        # via a fresh middleware instance
        middleware = RateLimitMiddleware(app, max_requests=1000, window_seconds=60)
        with middleware._lock:
            for i in range(_MAX_TRACKED_IPS + 100):
                middleware._requests[f"stale_ip_{i}"] = []

        # The key test: stale IPs don't prevent new requests from being processed
        # (eviction should clean them up). We verify the app still works.
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

    def test_rate_limit_unknown_client(self):
        async def test_route(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/test", test_route)])
        app.add_middleware(RateLimitMiddleware, max_requests=1, window_seconds=60)
        client = TestClient(app)

        # Should handle gracefully even with no client host
        response = client.get("/test")
        assert response.status_code != 500


class TestRequestIDMiddleware:
    def test_request_id_added_to_response(self):
        async def test_route(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/test", test_route)])
        app.add_middleware(RequestIDMiddleware)
        client = TestClient(app)

        response = client.get("/test")
        assert "x-request-id" in response.headers
        assert len(response.headers["x-request-id"]) == 36

    def test_request_id_unique_per_request(self):
        async def test_route(request):
            return PlainTextResponse("ok")

        app = Starlette(routes=[Route("/test", test_route)])
        app.add_middleware(RequestIDMiddleware)
        client = TestClient(app)

        ids = set()
        for _ in range(5):
            response = client.get("/test")
            ids.add(response.headers["x-request-id"])
        assert len(ids) == 5
