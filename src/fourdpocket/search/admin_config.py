"""Admin-override resolution for search settings.

Mirrors the pattern in `fourdpocket.ai.factory`: .env defaults layered under
admin-panel overrides stored in `InstanceSettings.extra["search_config"]`.
"""

from __future__ import annotations

import logging

from fourdpocket.config import get_settings

logger = logging.getLogger(__name__)


def get_search_overrides_from_db() -> dict:
    """Read admin search config overrides from InstanceSettings.extra['search_config'].

    Returns empty dict if no overrides are set or DB is not available.
    """
    try:
        from sqlmodel import Session

        from fourdpocket.db.session import get_engine
        from fourdpocket.models.instance_settings import InstanceSettings

        engine = get_engine()
        with Session(engine) as db:
            settings = db.get(InstanceSettings, 1)
            if settings and settings.extra:
                return settings.extra.get("search_config", {})
    except Exception as e:
        logger.debug("Could not read search overrides from DB: %s", e)
    return {}


def get_resolved_search_config() -> dict:
    """Return merged search config: env defaults + admin DB overrides.

    Admin DB overrides take precedence over env vars. Bools are respected
    even when set to False (unlike AI config, which skips empty strings).
    """
    settings = get_settings()
    base = {
        "graph_ranker_enabled": settings.search.graph_ranker_enabled,
        "graph_ranker_hop_decay": settings.search.graph_ranker_hop_decay,
        "graph_ranker_top_k": settings.search.graph_ranker_top_k,
    }
    overrides = get_search_overrides_from_db()
    for key, value in overrides.items():
        if key in base and value is not None:
            base[key] = value
    return base
