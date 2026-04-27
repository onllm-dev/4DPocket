"""Backup operation — creates a tar.gz snapshot of the SQLite DB, secret key, and uploads.

Refuses to run if backend or worker processes are alive (hot DB guard).
Refuses for PostgreSQL (user must run pg_dump themselves).
Refuses to overwrite an existing output file.
"""

import sys
import tarfile
from pathlib import Path


def _is_process_running(name: str) -> bool:
    """Return True if the named process (backend/worker) appears to be running.

    Reads PID files from the CLI's PID_DIR.  Kept as a top-level function so
    tests can monkeypatch it without touching the real process table.
    """
    from fourdpocket.cli import _is_running as cli_is_running

    pid_name_map = {
        "backend": "server",
        "worker": "worker",
        "server": "server",
    }
    pid_name = pid_name_map.get(name, name)
    return cli_is_running(pid_name) is not None


def run_backup(
    *,
    db_url: str,
    storage_base: str,
    out_path: Path,
    vector_backend: str,
) -> None:
    """Create a tar.gz backup at *out_path*.

    Args:
        db_url: The configured database URL.
        storage_base: FDP_STORAGE__BASE_PATH value.
        out_path: Destination archive path.
        vector_backend: Resolved vector backend name (e.g. "chroma").

    Raises:
        SystemExit(1) on any precondition failure.
    """
    # ── Guard: Postgres ────────────────────────────────────────────
    if db_url.startswith("postgresql") or db_url.startswith("postgres"):
        print(
            "ERROR: PostgreSQL backup is not supported by this command.\n"
            "Use pg_dump directly:\n"
            f"  pg_dump '{db_url}' > backup.sql\n"
            "or with Docker:\n"
            "  docker exec 4dp-postgres pg_dump -U 4dp 4dpocket > backup.sql",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Guard: hot processes ───────────────────────────────────────
    running = [n for n in ("backend", "worker") if _is_process_running(n)]
    if running:
        print(
            f"ERROR: The following service(s) are running: {', '.join(running)}.\n"
            "Stop them first to avoid backing up a hot database:\n"
            "  ./app.sh stop --backend --worker",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Guard: refuse overwrite ────────────────────────────────────
    if out_path.exists():
        print(
            f"ERROR: Output file already exists: {out_path}\n"
            "Choose a different path or remove the existing file.",
            file=sys.stderr,
        )
        sys.exit(1)

    out_path.parent.mkdir(parents=True, exist_ok=True)

    base = Path(storage_base)

    # ── Collect paths to bundle ────────────────────────────────────
    db_path = Path(db_url.replace("sqlite:///", ""))

    secret_key_file = base / ".secret" / "secret_key"
    uploads_dir = base / "uploads"
    chroma_dir = base / "chromadb"

    with tarfile.open(out_path, "w:gz") as tf:
        # SQLite DB
        if db_path.exists():
            tf.add(db_path, arcname=f"db/{db_path.name}")
            # WAL/SHM side-files if present
            for suffix in ("-wal", "-shm"):
                side = Path(str(db_path) + suffix)
                if side.exists():
                    tf.add(side, arcname=f"db/{side.name}")

        # Secret key
        if secret_key_file.exists():
            tf.add(secret_key_file, arcname=".secret/secret_key")

        # Uploads directory
        if uploads_dir.exists():
            tf.add(uploads_dir, arcname="uploads")

        # ChromaDB persist dir (only when chroma vector backend is in use)
        if vector_backend == "chroma" and chroma_dir.exists():
            tf.add(chroma_dir, arcname="chromadb")

    size_bytes = out_path.stat().st_size
    if size_bytes >= 1_048_576:
        size_str = f"{size_bytes / 1_048_576:.1f} MB"
    elif size_bytes >= 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes} bytes"

    print(f"Backup complete: {out_path}  ({size_str})")
