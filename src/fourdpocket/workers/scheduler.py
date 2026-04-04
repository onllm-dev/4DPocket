"""Periodic scheduled tasks."""

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from huey import crontab

from fourdpocket.config import get_settings
from fourdpocket.workers import huey

logger = logging.getLogger(__name__)


@huey.periodic_task(crontab(hour="*/6"))
def cleanup_stale_tasks():
    """Clean up orphaned task data. Runs every 6 hours."""
    logger.info("Running stale task cleanup")
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
