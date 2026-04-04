"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

        from fourdpocket.search.sqlite_fts import init_fts, init_notes_fts, reindex_all_items

        with Session(get_engine()) as db:
            recreated = init_fts(db)
            init_notes_fts(db)
            if recreated:
                reindex_all_items(db)

    yield


app = FastAPI(
    title="4DPocket",
    description="Self-hosted AI-powered personal knowledge base",
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
has_wildcard = "*" in settings.server.cors_origins
if has_wildcard:
    logger.warning(
        "CORS wildcard '*' detected - credentials disabled for security"
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.server.cors_origins,
    allow_credentials=not has_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
app.add_middleware(RequestIDMiddleware)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    return response


# Mount frontend static files if build directory exists
frontend_dist = Path("frontend/dist")
if frontend_dist.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dist)), name="static")


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}


# Import and include API router after app creation to avoid circular imports
from fourdpocket.api.router import api_router  # noqa: E402

app.include_router(api_router)
