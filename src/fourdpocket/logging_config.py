"""Structured logging configuration.

Call configure_logging(json=True/False) once at application startup (before
the FastAPI app is created) to install the appropriate log formatter.

JSON mode emits one JSON object per line:
    {"ts": "...", "level": "INFO", "logger": "...", "msg": "...", "request_id": "..."}

The request_id field is pulled from the contextvars.ContextVar set by
RequestIDMiddleware; it defaults to null when no request context is active
(e.g. startup/shutdown log lines).
"""

import json
import logging
import sys
import traceback
from datetime import UTC, datetime


class _JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        from fourdpocket.middleware.request_id import request_id_var

        exc_text: str | None = None
        if record.exc_info:
            exc_text = "".join(traceback.format_exception(*record.exc_info))

        doc = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(None),
        }
        if exc_text:
            doc["exc"] = exc_text

        return json.dumps(doc, ensure_ascii=False)


def configure_logging(json: bool = False) -> None:
    """Configure root logger.

    Parameters
    ----------
    json:
        When True, use structured JSON output suitable for log aggregators
        (e.g. Loki, CloudWatch, Datadog).  When False, use the standard
        human-readable format.
    """
    if json:
        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
