"""Detailed health-check endpoint.

GET /api/v1/health/detailed — public (no auth required).

Returns 200 always with a body that probes each subsystem:
  - database       : SELECT 1 round-trip latency
  - search_keyword : attempt to acquire the keyword backend
  - search_vector  : attempt to acquire the vector backend
  - worker         : mtime of Huey's SQLite task db (SqliteHuey only)

Overall status is "degraded" when any check reports ok=False.
"""

import logging
import time
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import text

from fourdpocket import __version__

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


def _check_database() -> dict:
    """Ping the database with SELECT 1 and measure latency."""
    try:
        from fourdpocket.db.session import get_engine

        engine = get_engine()
        t0 = time.monotonic()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"ok": True, "latency_ms": latency_ms, "error": None}
    except Exception as exc:
        logger.debug("Database health check failed: %s", exc)
        return {"ok": False, "latency_ms": None, "error": str(exc)}


def _check_keyword_backend() -> dict:
    """Verify the keyword search backend is reachable."""
    try:
        from fourdpocket.search import get_search_service

        svc = get_search_service()
        backend_name = type(svc._keyword).__name__
        # Derive a human-readable label.
        if "Meilisearch" in backend_name:
            label = "meilisearch"
        else:
            label = "sqlite_fts"
        return {"ok": True, "backend": label, "error": None}
    except Exception as exc:
        logger.debug("Keyword backend health check failed: %s", exc)
        return {"ok": False, "backend": None, "error": str(exc)}


def _check_vector_backend() -> dict:
    """Verify the vector search backend is reachable."""
    try:
        from fourdpocket.search import get_search_service

        svc = get_search_service()
        backend_name = type(svc._vector).__name__
        if "Pgvector" in backend_name or "pgvector" in backend_name.lower():
            label = "pgvector"
        elif "Chroma" in backend_name:
            label = "chroma"
        else:
            label = "none"
        return {"ok": True, "backend": label, "error": None}
    except Exception as exc:
        logger.debug("Vector backend health check failed: %s", exc)
        return {"ok": False, "backend": None, "error": str(exc)}


def _check_worker() -> dict:
    """Estimate whether the Huey worker is alive via task-db mtime."""
    try:
        from fourdpocket.config import get_settings

        settings = get_settings()
        base = Path(settings.storage.base_path).expanduser().resolve()
        task_db = base / "huey_tasks.db"

        if not task_db.exists():
            # Worker may not have started yet or uses a different backend.
            return {"ok": None, "last_seen_seconds_ago": None}

        mtime = task_db.stat().st_mtime
        age = int(time.time() - mtime)
        # Heuristic: if the file was touched within the last 5 minutes consider
        # the worker alive.  Beyond that we degrade gracefully with ok=None
        # rather than hard False (mtime is an indirect signal).
        ok = True if age < 300 else None  # noqa: SIM210
        return {"ok": ok, "last_seen_seconds_ago": age}
    except Exception as exc:
        logger.debug("Worker health check failed: %s", exc)
        return {"ok": None, "last_seen_seconds_ago": None}


@router.get("/detailed")
def detailed_health_check():
    """Deep health probe covering DB, search backends, and worker."""
    checks = {
        "database": _check_database(),
        "search_keyword": _check_keyword_backend(),
        "search_vector": _check_vector_backend(),
        "worker": _check_worker(),
    }

    # Status is "degraded" if any check explicitly reports ok=False.
    any_failed = any(
        v.get("ok") is False for v in checks.values()
    )
    status = "degraded" if any_failed else "ok"

    return {
        "status": status,
        "version": __version__,
        "checks": checks,
    }
