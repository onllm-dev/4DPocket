"""Periodic tasks — RSS polling, cleanup, etc. (Phase 2 stubs)."""

import logging

from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.periodic_task(huey.crontab(hour="*/6"))
def cleanup_stale_tasks():
    """Clean up orphaned task data. Runs every 6 hours."""
    logger.info("Running stale task cleanup")
    # Phase 2: implement cleanup logic
