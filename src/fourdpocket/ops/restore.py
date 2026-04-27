"""Restore operation — untars a backup archive into storage + DB locations.

Preconditions:
  - --force flag required (prevents accidental data loss).
  - Backend and worker must be stopped.

Creates a .pre-restore-<ts>.tar.gz snapshot of current state before extracting
so the user can roll back if something goes wrong.
"""

import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def _is_process_running(name: str) -> bool:
    """Return True if the named process appears to be running.

    Separate from backup._is_process_running so tests can patch independently.
    """
    from fourdpocket.cli import _is_running as cli_is_running

    pid_name_map = {
        "backend": "server",
        "worker": "worker",
        "server": "server",
    }
    pid_name = pid_name_map.get(name, name)
    return cli_is_running(pid_name) is not None


def _post_restore_reinit(db_url: str) -> None:
    """Reset the engine singleton and run Alembic migrations after restore."""
    import subprocess

    from fourdpocket.db.session import reset_engine

    reset_engine()

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
    )


def run_restore(
    *,
    archive_path: Path,
    db_url: str,
    storage_base: str,
    backup_dir: Path,
    force: bool,
) -> None:
    """Restore from *archive_path*.

    Args:
        archive_path: Path to the backup tar.gz.
        db_url: The configured database URL.
        storage_base: FDP_STORAGE__BASE_PATH value.
        backup_dir: Directory where the pre-restore snapshot is written.
        force: Must be True or the operation is refused.

    Raises:
        SystemExit(1) on any precondition failure.
    """
    # ── Guard: --force required ────────────────────────────────────
    if not force:
        print(
            "ERROR: --force is required to restore a backup.\n"
            "This operation WILL OVERWRITE your current database and uploads.\n"
            "Run with --force to confirm.",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Guard: hot processes ───────────────────────────────────────
    running = [n for n in ("backend", "worker") if _is_process_running(n)]
    if running:
        print(
            f"ERROR: The following service(s) are running: {', '.join(running)}.\n"
            "Stop them first:\n"
            "  ./app.sh stop --backend --worker",
            file=sys.stderr,
        )
        sys.exit(1)

    if not archive_path.exists():
        print(f"ERROR: Archive not found: {archive_path}", file=sys.stderr)
        sys.exit(1)

    base = Path(storage_base)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # ── Pre-restore snapshot ───────────────────────────────────────
    backup_dir.mkdir(parents=True, exist_ok=True)
    pre_restore_path = backup_dir / f".pre-restore-{ts}.tar.gz"

    db_path = None
    if db_url.startswith("sqlite"):
        db_path = Path(db_url.replace("sqlite:///", ""))

    with tarfile.open(pre_restore_path, "w:gz") as tf:
        if db_path and db_path.exists():
            tf.add(db_path, arcname=f"db/{db_path.name}")
            for suffix in ("-wal", "-shm"):
                side = Path(str(db_path) + suffix)
                if side.exists():
                    tf.add(side, arcname=f"db/{side.name}")

        secret_key_file = base / ".secret" / "secret_key"
        if secret_key_file.exists():
            tf.add(secret_key_file, arcname=".secret/secret_key")

        uploads_dir = base / "uploads"
        if uploads_dir.exists():
            tf.add(uploads_dir, arcname="uploads")

        chroma_dir = base / "chromadb"
        if chroma_dir.exists():
            tf.add(chroma_dir, arcname="chromadb")

    print(f"Pre-restore snapshot saved: {pre_restore_path}")

    # ── Extract archive ────────────────────────────────────────────
    # Extract db/ → DB parent directory; everything else → storage_base
    with tarfile.open(archive_path, "r:gz") as tf:
        for member in tf.getmembers():
            if member.name.startswith("db/"):
                if db_path is not None:
                    target = db_path.parent / Path(member.name).name
                    member_f = tf.extractfile(member)
                    if member_f is not None:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(member_f.read())
            else:
                # Extract relative to storage_base
                # Use filter="data" when available (Python 3.12+) for safety
                target_dir = base
                target_dir.mkdir(parents=True, exist_ok=True)
                try:
                    tf.extract(member, path=target_dir, filter="data")
                except TypeError:
                    # Python < 3.12 doesn't support filter kwarg
                    tf.extract(member, path=target_dir)  # nosec

    # ── Post-restore re-init ───────────────────────────────────────
    print("Running post-restore database migrations...")
    _post_restore_reinit(db_url)

    print("Restore complete.")
    print(f"If something went wrong, roll back with: ./app.sh db restore --from {pre_restore_path} --force")
