"""Tests for db backup and db restore CLI commands.

Regression tests for: backup refuses hot DB, restore requires --force,
backup refuses overwrite, restore creates pre-restore snapshot.
"""

import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fourdpocket import cli


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def ops_env(tmp_path, monkeypatch):
    """Set up a self-contained environment for ops tests."""
    data_dir = tmp_path / "data"
    db_dir = data_dir / "db"
    db_dir.mkdir(parents=True)
    db_file = db_dir / "4dpocket.db"
    db_file.write_bytes(b"SQLite format 3\x00fake-db-content")

    secret_dir = data_dir / ".secret"
    secret_dir.mkdir()
    secret_file = secret_dir / "secret_key"
    secret_file.write_text("supersecretkey")
    secret_file.chmod(0o600)

    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir()
    (uploads_dir / "sample.txt").write_text("user upload")

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    # Patch PID_DIR so _is_running reads from our tmp_path
    pid_dir = tmp_path / "run"
    pid_dir.mkdir()
    monkeypatch.setattr(cli, "PID_DIR", pid_dir)
    monkeypatch.setattr(cli, "LOG_DIR", tmp_path / "logs")

    return {
        "tmp_path": tmp_path,
        "data_dir": data_dir,
        "db_file": db_file,
        "secret_file": secret_file,
        "uploads_dir": uploads_dir,
        "backup_dir": backup_dir,
        "pid_dir": pid_dir,
    }


def _make_args(**kwargs):
    """Build a namespace with defaults for backup/restore args."""
    import argparse
    defaults = {
        "out": None,
        "from_path": None,
        "force": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


# ─── Backup: server must be stopped ───────────────────────────────────────────


class TestBackupRefusesHotServer:
    def test_refuses_when_backend_running(self, ops_env, monkeypatch):
        """Backup should refuse if backend is running."""
        from fourdpocket.ops import backup as backup_mod

        pid_file = ops_env["pid_dir"] / "backend.pid"
        pid_file.write_text("99999999")  # Fake PID that doesn't exist

        # Simulate _is_running by making it think backend is alive
        monkeypatch.setattr(
            "fourdpocket.ops.backup._is_process_running",
            lambda name: name == "backend",
        )

        out = ops_env["backup_dir"] / "test.tar.gz"
        with pytest.raises(SystemExit) as exc:
            backup_mod.run_backup(
                db_url=f"sqlite:///{ops_env['db_file']}",
                storage_base=str(ops_env["data_dir"]),
                out_path=out,
                vector_backend="chroma",
            )
        assert exc.value.code != 0

    def test_refuses_when_worker_running(self, ops_env, monkeypatch):
        """Backup should refuse if worker is running."""
        from fourdpocket.ops import backup as backup_mod

        monkeypatch.setattr(
            "fourdpocket.ops.backup._is_process_running",
            lambda name: name == "worker",
        )

        out = ops_env["backup_dir"] / "test.tar.gz"
        with pytest.raises(SystemExit) as exc:
            backup_mod.run_backup(
                db_url=f"sqlite:///{ops_env['db_file']}",
                storage_base=str(ops_env["data_dir"]),
                out_path=out,
                vector_backend="chroma",
            )
        assert exc.value.code != 0


# ─── Backup: Postgres refused ─────────────────────────────────────────────────


class TestBackupRefusesPostgres:
    def test_refuses_postgres_db_url(self, ops_env, monkeypatch):
        """Backup should refuse to back up a PostgreSQL database."""
        from fourdpocket.ops import backup as backup_mod

        monkeypatch.setattr(
            "fourdpocket.ops.backup._is_process_running", lambda name: False
        )

        out = ops_env["backup_dir"] / "pg.tar.gz"
        with pytest.raises(SystemExit) as exc:
            backup_mod.run_backup(
                db_url="postgresql://user:pass@localhost:5432/mydb",
                storage_base=str(ops_env["data_dir"]),
                out_path=out,
                vector_backend="pgvector",
            )
        assert exc.value.code != 0


# ─── Backup: refuse to overwrite ──────────────────────────────────────────────


class TestBackupRefusesOverwrite:
    def test_refuses_existing_out_file(self, ops_env, monkeypatch):
        """Backup should refuse if OUT already exists."""
        from fourdpocket.ops import backup as backup_mod

        monkeypatch.setattr(
            "fourdpocket.ops.backup._is_process_running", lambda name: False
        )

        out = ops_env["backup_dir"] / "existing.tar.gz"
        out.write_bytes(b"old backup")  # pre-existing file

        with pytest.raises(SystemExit) as exc:
            backup_mod.run_backup(
                db_url=f"sqlite:///{ops_env['db_file']}",
                storage_base=str(ops_env["data_dir"]),
                out_path=out,
                vector_backend="chroma",
            )
        assert exc.value.code != 0


# ─── Backup: happy path ───────────────────────────────────────────────────────


class TestBackupHappyPath:
    def test_creates_tarball_with_expected_members(self, ops_env, monkeypatch):
        """Backup creates a tar.gz containing db, secret_key, uploads."""
        from fourdpocket.ops import backup as backup_mod

        monkeypatch.setattr(
            "fourdpocket.ops.backup._is_process_running", lambda name: False
        )

        out = ops_env["backup_dir"] / "ok.tar.gz"
        backup_mod.run_backup(
            db_url=f"sqlite:///{ops_env['db_file']}",
            storage_base=str(ops_env["data_dir"]),
            out_path=out,
            vector_backend="chroma",
        )

        assert out.exists()
        with tarfile.open(out, "r:gz") as tf:
            names = tf.getnames()

        # Must include db file
        assert any("4dpocket.db" in n for n in names), f"DB not in archive: {names}"
        # Must include secret_key
        assert any("secret_key" in n for n in names), f"secret_key not in archive: {names}"
        # Must include uploads
        assert any("uploads" in n for n in names), f"uploads not in archive: {names}"

    def test_prints_final_size(self, ops_env, monkeypatch, capsys):
        """Backup prints file size on success."""
        from fourdpocket.ops import backup as backup_mod

        monkeypatch.setattr(
            "fourdpocket.ops.backup._is_process_running", lambda name: False
        )

        out = ops_env["backup_dir"] / "sized.tar.gz"
        backup_mod.run_backup(
            db_url=f"sqlite:///{ops_env['db_file']}",
            storage_base=str(ops_env["data_dir"]),
            out_path=out,
            vector_backend="chroma",
        )

        captured = capsys.readouterr()
        assert "bytes" in captured.out.lower() or "kb" in captured.out.lower() or str(out) in captured.out


# ─── Restore: requires --force ────────────────────────────────────────────────


class TestRestoreRequiresForce:
    def test_refuses_without_force(self, ops_env, monkeypatch):
        """Restore should refuse without --force flag."""
        from fourdpocket.ops import restore as restore_mod

        monkeypatch.setattr(
            "fourdpocket.ops.restore._is_process_running", lambda name: False
        )

        dummy_archive = ops_env["backup_dir"] / "snap.tar.gz"
        dummy_archive.write_bytes(b"fake archive")

        with pytest.raises(SystemExit) as exc:
            restore_mod.run_restore(
                archive_path=dummy_archive,
                db_url=f"sqlite:///{ops_env['db_file']}",
                storage_base=str(ops_env["data_dir"]),
                backup_dir=ops_env["backup_dir"],
                force=False,
            )
        assert exc.value.code != 0


# ─── Restore: refuses hot processes ───────────────────────────────────────────


class TestRestoreRefusesHotProcesses:
    def test_refuses_when_backend_running(self, ops_env, monkeypatch):
        """Restore should refuse if backend is running."""
        from fourdpocket.ops import restore as restore_mod

        monkeypatch.setattr(
            "fourdpocket.ops.restore._is_process_running",
            lambda name: name == "backend",
        )

        dummy_archive = ops_env["backup_dir"] / "snap.tar.gz"
        dummy_archive.write_bytes(b"fake archive")

        with pytest.raises(SystemExit) as exc:
            restore_mod.run_restore(
                archive_path=dummy_archive,
                db_url=f"sqlite:///{ops_env['db_file']}",
                storage_base=str(ops_env["data_dir"]),
                backup_dir=ops_env["backup_dir"],
                force=True,
            )
        assert exc.value.code != 0


# ─── Restore: happy path ──────────────────────────────────────────────────────


class TestRestoreHappyPath:
    def test_creates_pre_restore_snapshot_and_extracts(self, ops_env, monkeypatch):
        """Restore creates a pre-restore snapshot then extracts the archive."""
        from fourdpocket.ops import backup as backup_mod
        from fourdpocket.ops import restore as restore_mod

        monkeypatch.setattr(
            "fourdpocket.ops.backup._is_process_running", lambda name: False
        )
        monkeypatch.setattr(
            "fourdpocket.ops.restore._is_process_running", lambda name: False
        )

        # Stub out reset_engine and alembic
        monkeypatch.setattr(
            "fourdpocket.ops.restore._post_restore_reinit",
            lambda db_url: None,
        )

        # Create a real backup first
        archive = ops_env["backup_dir"] / "snap.tar.gz"
        backup_mod.run_backup(
            db_url=f"sqlite:///{ops_env['db_file']}",
            storage_base=str(ops_env["data_dir"]),
            out_path=archive,
            vector_backend="chroma",
        )

        # Now restore it
        restore_mod.run_restore(
            archive_path=archive,
            db_url=f"sqlite:///{ops_env['db_file']}",
            storage_base=str(ops_env["data_dir"]),
            backup_dir=ops_env["backup_dir"],
            force=True,
        )

        # Pre-restore snapshot must exist
        pre_restores = list(ops_env["backup_dir"].glob(".pre-restore-*.tar.gz"))
        assert len(pre_restores) >= 1, "No pre-restore snapshot created"
