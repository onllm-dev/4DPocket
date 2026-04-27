"""Tests for RequestIDMiddleware.

Covers:
  - New UUID4 generated when no header supplied.
  - Incoming X-Request-ID is echoed back unchanged.
  - request.state.request_id is set correctly.
  - request_id contextvar is populated during handler execution.
  - IDs are unique across separate requests.
"""

import re
import uuid

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from fourdpocket.middleware.request_id import RequestIDMiddleware, request_id_var

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _make_app():
    async def handler(request: Request):
        state_id = getattr(request.state, "request_id", None)
        ctx_id = request_id_var.get(None)
        return PlainTextResponse(f"{state_id}|{ctx_id}")

    app = Starlette(routes=[Route("/", handler)])
    app.add_middleware(RequestIDMiddleware)
    return app


class TestRequestIDMiddleware:
    def test_generates_uuid_when_no_header(self):
        """A fresh UUID4 is generated if X-Request-ID is not in the request."""
        client = TestClient(_make_app())
        response = client.get("/")
        assert response.status_code == 200
        rid = response.headers["x-request-id"]
        assert _UUID_RE.match(rid), f"Expected UUID4 but got: {rid}"

    def test_echoes_incoming_request_id(self):
        """An X-Request-ID supplied by the caller is echoed back unchanged."""
        custom_id = "my-trace-12345"
        client = TestClient(_make_app())
        response = client.get("/", headers={"X-Request-ID": custom_id})
        assert response.headers["x-request-id"] == custom_id

    def test_request_state_and_contextvar_match(self):
        """request.state.request_id and the contextvar hold the same value."""
        client = TestClient(_make_app())
        response = client.get("/")
        rid = response.headers["x-request-id"]
        state_id, ctx_id = response.text.split("|")
        assert state_id == rid
        assert ctx_id == rid

    def test_unique_ids_per_request(self):
        """Each request receives a distinct request ID."""
        client = TestClient(_make_app())
        ids = {client.get("/").headers["x-request-id"] for _ in range(5)}
        assert len(ids) == 5, "Expected 5 distinct request IDs"

    def test_contextvar_cleared_after_request(self):
        """The contextvar is reset to None once the request is complete."""
        client = TestClient(_make_app())
        client.get("/")
        # After the response the token was reset — contextvar should be None
        # in this (non-request) context.
        assert request_id_var.get(None) is None
