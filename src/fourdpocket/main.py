"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fourdpocket import __version__
from fourdpocket.api.middleware import RateLimitMiddleware, RequestIDMiddleware
from fourdpocket.config import get_settings
from fourdpocket.db.session import get_engine, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    data_dir = Path(settings.storage.base_path)
    data_dir.mkdir(parents=True, exist_ok=True)
    init_db()

    # Initialize FTS5 search only when both the search backend and database are SQLite
    if settings.search.backend == "sqlite" and settings.database.url.startswith("sqlite"):
        from sqlmodel import Session

        from fourdpocket.search.sqlite_fts import (
            init_chunks_fts,
            init_fts,
            init_notes_fts,
            reindex_all_items,
        )

        with Session(get_engine()) as db:
            recreated = init_fts(db)
            init_notes_fts(db)
            init_chunks_fts(db)
            if recreated:
                reindex_all_items(db)

    # Start Huey worker automatically
    import subprocess
    import sys

    huey_process = subprocess.Popen(
        [sys.executable, "-m", "fourdpocket.workers.huey_worker"],
    )
    logger.info("Started Huey worker (PID %s)", huey_process.pid)

    # Start the MCP session manager (streamable-HTTP transport at /mcp).
    # The manager is stateful and only supports a single run() per instance,
    # so we skip it under pytest (which re-enters the lifespan per test).
    import sys as _sys

    if "pytest" in _sys.modules:
        try:
            yield
        finally:
            huey_process.terminate()
            huey_process.wait()
    else:
        from fourdpocket.mcp import mcp

        async with mcp.session_manager.run():
            try:
                yield
            finally:
                huey_process.terminate()
                huey_process.wait()


app = FastAPI(
    title="4DPocket",
    description="Self-hosted AI-powered personal knowledge base",
    version=__version__,
    lifespan=lifespan,
)

settings = get_settings()
has_wildcard = "*" in settings.server.cors_origins
if has_wildcard:
    logger.warning(
        "CORS wildcard '*' detected - credentials disabled for security"
    )


class ExtensionCORSMiddleware(CORSMiddleware):
    """CORS middleware that also allows browser extension origins.

    Chrome/Edge extensions use ``chrome-extension://<id>`` and Firefox
    extensions use ``moz-extension://<id>``.  The extension ID changes per
    install, so we allow all of them automatically.
    """

    def is_allowed_origin(self, origin: str) -> bool:
        if origin.startswith(("chrome-extension://", "moz-extension://")):
            return True
        return super().is_allowed_origin(origin=origin)


app.add_middleware(
    ExtensionCORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=not has_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60, trust_proxy=settings.server.trust_proxy)
app.add_middleware(RequestIDMiddleware)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    return response


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}


# Import and include API router after app creation to avoid circular imports
from fourdpocket.api.router import api_router  # noqa: E402

app.include_router(api_router)

# Mount the MCP server at /mcp. Import-time attachment is safe because the
# ``FastMCP`` session manager is activated inside the lifespan above.
from fastapi.responses import RedirectResponse  # noqa: E402

from fourdpocket.mcp import build_mcp_app  # noqa: E402


# The mounted ASGI app only answers at ``/mcp/`` (trailing slash). Most
# users configure clients with ``http://host/mcp`` — redirect so both work.
@app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=False)
def _mcp_trailing_slash():
    # 307 preserves the HTTP method + body, which is required for MCP POSTs.
    return RedirectResponse(url="/mcp/", status_code=307)


app.mount("/mcp", build_mcp_app())

# SPA catch-all: must be registered AFTER API routes
# Try package-bundled static files first (pip install), then dev path (app.sh / source)
_pkg_static = Path(__file__).parent / "static"
frontend_dist = _pkg_static if _pkg_static.is_dir() else Path("frontend/dist")
if frontend_dist.exists():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if ".." not in full_path:
            file_path = frontend_dist / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
