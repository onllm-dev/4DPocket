"""Periodic scheduled tasks."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from huey import crontab
from sqlmodel import Session, select

from fourdpocket.config import get_settings
from fourdpocket.models.base import ItemType
from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.periodic_task(crontab(hour="*/6"))
def cleanup_stale_tasks():
    """Clean up orphaned task data. Runs every 6 hours."""
    logger.info("Running stale task cleanup")
    # Phase 2: implement cleanup logic


@huey.periodic_task(crontab(minute="*/15"))
def reprocess_pending_items():
    """Find items with processing errors or missing content and re-enqueue.

    Guardrails:
    - Max 20 items per run to avoid hammering the queue
    - Skip items that have been retried >3 times (tracked via item_metadata._retry_count)
    - Only process items created in the last 7 days (avoid ancient items)
    """
    from datetime import timedelta

    from fourdpocket.db.session import get_engine
    from fourdpocket.models.item import KnowledgeItem

    logger.info("Scanning for pending items to reprocess")
    engine = get_engine()
    with Session(engine) as db:
        since = datetime.now(timezone.utc) - timedelta(days=7)
        items = db.exec(
            select(KnowledgeItem).where(
                KnowledgeItem.created_at >= since,
                KnowledgeItem.content.is_(None),
                KnowledgeItem.item_type == ItemType.url,
            )
            .limit(200)
        ).all()

        enqueued = 0
        for item in items:
            retry_count = item.item_metadata.get("_retry_count", 0)
            if retry_count >= 3:
                logger.debug("Skipping item %s: max retries reached (%d)", item.id, retry_count)
                continue

            if item.url:
                from fourdpocket.workers.fetcher import fetch_and_process_url
                fetch_and_process_url(str(item.id), item.url, str(item.user_id))
                item.item_metadata["_retry_count"] = retry_count + 1
                db.add(item)
                enqueued += 1

        if enqueued:
            db.commit()
            logger.info("Enqueued %d pending items for reprocessing", enqueued)
    # Phase 2: implement cleanup logic


def run_backup() -> str | None:
    """Create a backup of the SQLite database and data directory."""
    settings = get_settings()

    # Only backup SQLite databases
    db_url = settings.database.url
    if "sqlite" not in db_url:
        logger.info("Backup skipped - only SQLite databases are backed up automatically")
        return None

    # Extract DB path from URL
    db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    if db_path.startswith("~"):
        db_path = str(Path(db_path).expanduser())

    if not Path(db_path).exists():
        logger.warning(f"Database file not found: {db_path}")
        return None

    # Create backup directory
    backup_dir = Path(settings.storage.base_path).expanduser() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped backup
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"4dpocket_backup_{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    logger.info(f"Backup created: {backup_path}")

    # Clean up old backups (keep last 10)
    backups = sorted(backup_dir.glob("4dpocket_backup_*.db"), reverse=True)
    for old_backup in backups[10:]:
        old_backup.unlink()
        logger.info(f"Removed old backup: {old_backup}")

    return str(backup_path)
