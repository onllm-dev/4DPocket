"""Request-ID middleware.

Reads X-Request-ID from incoming request headers (pass-through for tracing
from upstream proxies). Generates a UUID4 if no header is present. Stores
the value on request.state.request_id and in a contextvars.ContextVar so
structured loggers can include it without explicit passing.

Echoes the ID back in the X-Request-ID response header.
"""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Module-level contextvar — importable by logging_config and any other consumer.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a request-ID to every request and echo it in the response."""

    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        request_id = incoming if incoming else str(uuid.uuid4())

        request.state.request_id = request_id
        token = request_id_var.set(request_id)

        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)

        response.headers["X-Request-ID"] = request_id
        return response
