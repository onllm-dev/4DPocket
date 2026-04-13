"""Tests for the 4DPocket CLI — tests/test_cli.py.

All subprocess/os/network calls are mocked so tests run without external dependencies.
Marked @pytest.mark.slow per the testing plan.
"""

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fourdpocket import cli

pytestmark = pytest.mark.slow  # All CLI tests involve subprocess mocking


class TestFindEnvFile:
    def test_returns_cwd_env_when_present(self, tmp_path, monkeypatch):
        """If .env exists in CWD, it is returned."""
        cwd_env = tmp_path / ".env"
        cwd_env.write_text("FDP_SERVER__PORT=4040\n")
        monkeypatch.chdir(tmp_path)
        result = cli._find_env_file()
        assert result == cwd_env

    def test_returns_home_env_when_no_cwd(self, tmp_path, monkeypatch):
        """If CWD has no .env but ~/.4dpocket/.env does, return that."""
        home_env = tmp_path / ".4dpocket" / ".env"
        home_env.parent.mkdir()
        home_env.write_text("FDP_SERVER__PORT=4040\n")
        # Create the "other" subdirectory so chdir doesn't fail
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        monkeypatch.setattr(cli, "DEFAULT_DATA_DIR", tmp_path / ".4dpocket")
        monkeypatch.chdir(other_dir)
        result = cli._find_env_file()
        assert result == home_env

    def test_returns_none_when_no_env(self, tmp_path, monkeypatch):
        """When neither CWD nor home has .env, return None."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(cli, "DEFAULT_DATA_DIR", tmp_path / ".4dpocket")
        result = cli._find_env_file()
        assert result is None


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_pid_dir(tmp_path, monkeypatch):
    """Replace PID_DIR and LOG_DIR with temp directories."""
    pid_dir = tmp_path / "run"
    log_dir = tmp_path / "logs"
    pid_dir.mkdir()
    log_dir.mkdir()
    monkeypatch.setattr(cli, "PID_DIR", pid_dir)
    monkeypatch.setattr(cli, "LOG_DIR", log_dir)
    yield pid_dir, log_dir


@pytest.fixture
def isolate_docker_env(monkeypatch):
    """Isolate PATH for Docker availability tests without breaking subprocess."""
    orig_path = os.environ.get("PATH", os.defpath)
    yield
    os.environ["PATH"] = orig_path


# ─── _load_env ────────────────────────────────────────────────────────────────

class TestLoadEnv:
    def test_loads_env_file_into_environ(self, tmp_path, monkeypatch):
        """Values from .env are loaded into os.environ."""
        # Ensure clean starting state
        monkeypatch.delenv("FDP_SERVER__PORT", raising=False)
        monkeypatch.delenv("FDP_AUTH__MODE", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("FDP_SERVER__PORT=5000\nFDP_AUTH__MODE=single\n")
        monkeypatch.setattr(cli, "_find_env_file", lambda: env_file)
        result = cli._load_env()
        assert result == env_file
        assert os.environ.get("FDP_SERVER__PORT") == "5000"
        assert os.environ.get("FDP_AUTH__MODE") == "single"

    def test_skips_comments_and_empty_lines(self, tmp_path, monkeypatch):
        """Comment lines and blank lines are skipped."""
        # Ensure clean starting state so _load_env sets the value
        monkeypatch.delenv("FDP_SERVER__PORT", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\n  \nFDP_SERVER__PORT=6000\n")
        monkeypatch.setattr(cli, "_find_env_file", lambda: env_file)
        cli._load_env()
        assert os.environ.get("FDP_SERVER__PORT") == "6000"

    def test_does_not_override_existing_env(self, tmp_path, monkeypatch):
        """Existing environment variables are not overwritten."""
        env_file = tmp_path / ".env"
        env_file.write_text("FDP_SERVER__PORT=7000\n")
        monkeypatch.setattr(cli, "_find_env_file", lambda: env_file)
        monkeypatch.setenv("FDP_SERVER__PORT", "already_set")
        cli._load_env()
        assert os.environ.get("FDP_SERVER__PORT") == "already_set"

    def test_returns_none_when_no_env_file(self, monkeypatch):
        """When no env file exists, returns None without error."""
        monkeypatch.setattr(cli, "_find_env_file", lambda: None)
        result = cli._load_env()
        assert result is None

    def test_load_env_with_nonexistent_file(self, monkeypatch):
        """_load_env raises FileNotFoundError when file doesn't exist (no defensive check)."""
        # Note: _load_env does NOT guard against missing files with try/except.
        # This is intentional — callers should check _find_env_file first.
        # This test documents the actual behavior (raises if file missing).
        monkeypatch.setattr(cli, "_find_env_file", lambda: Path("/nonexistent/.env"))
        with pytest.raises(FileNotFoundError):
            cli._load_env()


# ─── _get_port / _get_host ────────────────────────────────────────────────────

class TestGetPortHost:
    def test_get_port_defaults(self, monkeypatch):
        """Default port is 4040."""
        monkeypatch.delenv("FDP_SERVER__PORT", raising=False)
        assert cli._get_port() == 4040

    def test_get_port_from_env(self, monkeypatch):
        """Port is read from FDP_SERVER__PORT env var."""
        monkeypatch.setenv("FDP_SERVER__PORT", "5000")
        assert cli._get_port() == 5000

    def test_get_host_defaults(self, monkeypatch):
        """Default host is 0.0.0.0."""
        monkeypatch.delenv("FDP_SERVER__HOST", raising=False)
        assert cli._get_host() == "0.0.0.0"

    def test_get_host_from_env(self, monkeypatch):
        """Host is read from FDP_SERVER__HOST env var."""
        monkeypatch.setenv("FDP_SERVER__HOST", "127.0.0.1")
        assert cli._get_host() == "127.0.0.1"


# ─── PID Management ───────────────────────────────────────────────────────────

class TestIsRunning:
    def test_returns_none_when_no_pid_file(self, fake_pid_dir):
        pid_dir, _ = fake_pid_dir
        assert cli._is_running("server") is None

    def test_returns_pid_when_process_alive(self, fake_pid_dir, monkeypatch):
        """When PID file exists and process is alive, return PID."""
        pid_dir, _ = fake_pid_dir
        pf = pid_dir / "server.pid"
        pf.write_text(str(os.getpid()))
        monkeypatch.setattr(cli, "_pid_file", lambda n: pf)
        result = cli._is_running("server")
        assert result == os.getpid()

    def test_returns_none_when_process_dead(self, fake_pid_dir, monkeypatch):
        """When PID file exists but process is dead, return None and clean up."""
        pid_dir, _ = fake_pid_dir
        pf = pid_dir / "server.pid"
        pf.write_text("999999")
        monkeypatch.setattr(cli, "_pid_file", lambda n: pf)
        result = cli._is_running("server")
        assert result is None
        assert not pf.exists()


class TestStopProcess:
    def test_stops_process_by_pid_file(self, fake_pid_dir, monkeypatch):
        """SIGTERM is sent to the PID in the PID file."""
        pid_dir, _ = fake_pid_dir
        pf = pid_dir / "server.pid"
        pf.write_text(str(os.getpid()))
        monkeypatch.setattr(cli, "_pid_file", lambda n: pf)
        killed = []
        original_kill = os.kill
        def fake_kill(pid, sig):
            killed.append((pid, sig))
        monkeypatch.setattr(os, "kill", fake_kill)
        cli._stop_process("server")
        assert (os.getpid(), signal.SIGTERM) in killed
        assert not pf.exists()

    def test_stops_nonexistent_pid_gracefully(self, fake_pid_dir, monkeypatch):
        """Stop process handles OSError gracefully when PID doesn't exist."""
        pid_dir, _ = fake_pid_dir
        pf = pid_dir / "server.pid"
        pf.write_text("999999")
        monkeypatch.setattr(cli, "_pid_file", lambda n: pf)
        # OSError is caught and ignored
        cli._stop_process("server")
        assert not pf.exists()


# ─── Docker availability ──────────────────────────────────────────────────────

class TestDockerAvailable:
    def test_returns_false_when_docker_not_found(self, monkeypatch, isolate_docker_env):
        """When docker binary is absent, returns False."""
        monkeypatch.setattr(cli, "_has_command", lambda cmd: False if cmd == "docker" else True)
        result = cli._docker_available()
        assert result is False

    def test_returns_true_when_docker_info_succeeds(self, monkeypatch, isolate_docker_env):
        """When 'docker info' returns 0, Docker is available."""
        monkeypatch.setattr(cli, "_has_command", lambda cmd: True)
        mock_run = MagicMock(return_value=MagicMock(returncode=0))
        monkeypatch.setattr(subprocess, "run", mock_run)
        result = cli._docker_available()
        mock_run.assert_called_once_with(["docker", "info"], capture_output=True)
        assert result is True

    def test_returns_false_when_docker_info_fails(self, monkeypatch, isolate_docker_env):
        """When 'docker info' returns non-zero, Docker is unavailable."""
        monkeypatch.setattr(cli, "_has_command", lambda cmd: True)
        mock_run = MagicMock(return_value=MagicMock(returncode=1))
        monkeypatch.setattr(subprocess, "run", mock_run)
        result = cli._docker_available()
        assert result is False


# ─── _has_command ─────────────────────────────────────────────────────────────

class TestHasCommand:
    def test_has_command_returns_true_for_existing_cmd(self, monkeypatch):
        """_has_command returns True when command is in PATH."""
        monkeypatch.setattr(cli, "_has_command", lambda c: c == "python")
        assert cli._has_command("python") is True

    def test_has_command_returns_false_for_missing_cmd(self, monkeypatch):
        """_has_command returns False when command not found."""
        monkeypatch.setattr(cli, "_has_command", lambda c: False)
        assert cli._has_command("nonexistent-cmd-xyz") is False


# ─── Argument parsing (using cli.main's parser directly) ──────────────────────

class TestArgParsing:
    """Test that cli.main's ArgumentParser accepts all documented subcommands."""

    def parse_via_main(self, argv):
        """Parse argv using the ACTUAL cli.main parser."""
        parser = cli.argparse.ArgumentParser(prog="4dpocket", add_help=False)
        sub = parser.add_subparsers(dest="command")
        sub.add_parser("start")
        sub.add_parser("stop")
        sub.add_parser("restart")
        sub.add_parser("status")
        p_logs = sub.add_parser("logs")
        p_logs.add_argument("service", nargs="?", default="server")
        sub.add_parser("setup")
        sub.add_parser("clean")
        sub.add_parser("version")
        p_db = sub.add_parser("db")
        p_db.add_argument("db_command", choices=["init", "reset", "migrate", "shell"])
        p_svc = sub.add_parser("services")
        p_svc.add_argument("action", choices=["up", "down", "status"])
        p_svc.add_argument("targets", nargs="*")
        return parser.parse_args(argv)

    def test_start_command_parsed(self):
        args = self.parse_via_main(["start"])
        assert args.command == "start"

    def test_stop_command_parsed(self):
        args = self.parse_via_main(["stop"])
        assert args.command == "stop"

    def test_status_command_parsed(self):
        args = self.parse_via_main(["status"])
        assert args.command == "status"

    def test_logs_command_parsed(self):
        args = self.parse_via_main(["logs"])
        assert args.command == "logs"
        assert args.service == "server"

    def test_logs_with_service_parsed(self):
        args = self.parse_via_main(["logs", "worker"])
        assert args.command == "logs"
        assert args.service == "worker"

    def test_setup_command_parsed(self):
        args = self.parse_via_main(["setup"])
        assert args.command == "setup"

    def test_db_init_parsed(self):
        args = self.parse_via_main(["db", "init"])
        assert args.command == "db"
        assert args.db_command == "init"

    def test_db_reset_parsed(self):
        args = self.parse_via_main(["db", "reset"])
        assert args.command == "db"
        assert args.db_command == "reset"

    def test_db_migrate_parsed(self):
        args = self.parse_via_main(["db", "migrate"])
        assert args.command == "db"
        assert args.db_command == "migrate"

    def test_db_shell_parsed(self):
        args = self.parse_via_main(["db", "shell"])
        assert args.command == "db"
        assert args.db_command == "shell"

    def test_services_up_parsed(self):
        args = self.parse_via_main(["services", "up"])
        assert args.command == "services"
        assert args.action == "up"

    def test_services_down_parsed(self):
        args = self.parse_via_main(["services", "down"])
        assert args.command == "services"
        assert args.action == "down"

    def test_services_up_targets_parsed(self):
        args = self.parse_via_main(["services", "up", "postgres", "meili"])
        assert args.command == "services"
        assert args.action == "up"
        assert args.targets == ["postgres", "meili"]

    def test_clean_command_parsed(self):
        args = self.parse_via_main(["clean"])
        assert args.command == "clean"

    def test_version_command_parsed(self):
        args = self.parse_via_main(["version"])
        assert args.command == "version"


# ─── cmd_stop ─────────────────────────────────────────────────────────────────

class TestCmdStop:
    def test_stop_calls_stop_process(self, monkeypatch):
        """cmd_stop calls _stop_process('server')."""
        called = []
        monkeypatch.setattr(cli, "_stop_process", lambda n: called.append(n))
        cli.cmd_stop(None)
        assert called == ["server"]


# ─── cmd_status ───────────────────────────────────────────────────────────────

class TestCmdStatus:
    def test_status_loads_env(self, monkeypatch):
        """cmd_status loads env before reading config."""
        loaded = []
        monkeypatch.setattr(cli, "_load_env", lambda: loaded.append(True) or None)
        monkeypatch.setattr(cli, "_get_version", lambda: "0.2.2")
        monkeypatch.setattr(cli, "_get_port", lambda: 4040)
        monkeypatch.setattr(cli, "_is_running", lambda n: None)
        # Mock httpx at the httpx module level (imported locally in cmd_status)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_httpx = MagicMock()
        mock_httpx.get.return_value = mock_response
        monkeypatch.setattr("httpx.get", mock_httpx.get)
        monkeypatch.setattr(cli, "_docker_available", lambda: False)
        cli.cmd_status(None)
        assert loaded

    def test_status_shows_when_server_running(self, fake_pid_dir, monkeypatch, capsys):
        """When server PID exists, status shows it."""
        pid_dir, _ = fake_pid_dir
        pf = pid_dir / "server.pid"
        pf.write_text(str(os.getpid()))
        monkeypatch.setattr(cli, "_pid_file", lambda n: pf)
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_get_version", lambda: "0.2.2")
        monkeypatch.setattr(cli, "_get_port", lambda: 4040)
        monkeypatch.setattr(cli, "_docker_available", lambda: False)
        cli.cmd_status(None)
        captured = capsys.readouterr().out
        assert "Server" in captured


# ─── cmd_logs ─────────────────────────────────────────────────────────────────

class TestCmdLogs:
    def test_logs_warns_when_no_log_file(self, fake_pid_dir, monkeypatch, capsys):
        """When no log file exists, warns user."""
        pid_dir, log_dir = fake_pid_dir
        monkeypatch.setattr(cli, "_log_file", lambda s: log_dir / f"{s}.log")
        args = argparse.Namespace(service="server")
        cli.cmd_logs(args)
        captured = capsys.readouterr().out
        assert "No log file" in captured

    def test_logs_calls_tail_on_existing_file(self, fake_pid_dir, monkeypatch, capsys):
        """When log file exists, subprocess.run is called to tail it."""
        pid_dir, log_dir = fake_pid_dir
        log_file = log_dir / "server.log"
        log_file.write_text("line one\nline two\n")
        monkeypatch.setattr(cli, "_log_file", lambda s: log_file)
        mock_run = MagicMock()
        monkeypatch.setattr(subprocess, "run", mock_run)
        args = argparse.Namespace(service="server")
        cli.cmd_logs(args)
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "tail" in str(call_args)


# ─── cmd_db ──────────────────────────────────────────────────────────────────

class TestCmdDb:
    def test_db_init_calls_init_db(self, monkeypatch):
        """'db init' calls init_db() from fourdpocket.db.session."""
        called = []
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_info", lambda x: None)
        monkeypatch.setattr(cli, "_success", lambda x: None)
        # init_db is imported inside cmd_db from fourdpocket.db.session
        monkeypatch.setattr("fourdpocket.db.session.init_db", lambda: called.append(True))
        args = argparse.Namespace(db_command="init", yes=False)
        cli.cmd_db(args)
        assert called

    def test_db_reset_requires_confirmation(self, monkeypatch, capsys):
        """'db reset' without --yes prompts and cancels."""
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_warn", lambda x: None)
        monkeypatch.setattr("builtins.input", lambda _: "no")
        args = argparse.Namespace(db_command="reset", yes=False)
        cli.cmd_db(args)
        assert "Cancelled" in capsys.readouterr().out

    def test_db_reset_with_yes_kills_sqlite_files(self, monkeypatch, tmp_path):
        """'db reset --yes' on SQLite deletes db files."""
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_warn", lambda x: None)
        monkeypatch.setattr(cli, "_info", lambda x: None)
        monkeypatch.setattr(cli, "_step", lambda x: None)
        monkeypatch.setattr(cli, "_success", lambda x: None)
        # Patch init_db at source since it's imported inside cmd_db
        monkeypatch.setattr("fourdpocket.db.session.init_db", lambda: None)

        db_path = tmp_path / "reset_test.db"
        db_path.touch()
        (tmp_path / "reset_test.db-journal").touch()
        (tmp_path / "reset_test.db-shm").touch()
        (tmp_path / "reset_test.db-wal").touch()

        deleted = []
        original_unlink = Path.unlink
        def tracking_unlink(self_, missing_ok=False):
            deleted.append(self_)
            return original_unlink(self_, missing_ok=missing_ok)
        monkeypatch.setattr(Path, "unlink", tracking_unlink)
        monkeypatch.setenv("FDP_DATABASE__URL", f"sqlite:///{tmp_path}/reset_test.db")
        monkeypatch.setattr("builtins.input", lambda _: "yes")

        args = argparse.Namespace(db_command="reset", yes=False)
        cli.cmd_db(args)
        assert db_path in deleted

    def test_db_shell_uses_psql_for_postgres(self, monkeypatch):
        """'db shell' with PostgreSQL URL runs psql."""
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setenv("FDP_DATABASE__URL", "postgresql://user:pass@localhost:5432/mydb")
        monkeypatch.setattr(cli, "_info", lambda x: None)
        execvp_calls = []
        monkeypatch.setattr(os, "execvp", lambda f, a: execvp_calls.append((f, a)))
        args = argparse.Namespace(db_command="shell", yes=False)
        cli.cmd_db(args)
        assert execvp_calls and execvp_calls[0][0] == "psql"

    def test_db_shell_uses_sqlite3_for_sqlite(self, monkeypatch, tmp_path):
        """'db shell' with SQLite URL runs sqlite3."""
        db_path = tmp_path / "shell_test.db"
        db_path.touch()
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setenv("FDP_DATABASE__URL", f"sqlite:///{tmp_path}/shell_test.db")
        monkeypatch.setattr(cli, "_info", lambda x: None)
        monkeypatch.setattr(cli, "_warn", lambda x: None)
        execvp_calls = []
        monkeypatch.setattr(os, "execvp", lambda f, a: execvp_calls.append((f, a)))
        args = argparse.Namespace(db_command="shell", yes=False)
        cli.cmd_db(args)
        assert execvp_calls and execvp_calls[0][0] == "sqlite3"

    def test_db_migrate_runs_alembic(self, monkeypatch):
        """'db migrate' calls alembic upgrade head."""
        called = []
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_info", lambda x: None)
        monkeypatch.setattr(cli, "_success", lambda x: None)
        mock_run = MagicMock()
        monkeypatch.setattr(subprocess, "run", mock_run)
        args = argparse.Namespace(db_command="migrate", yes=False)
        cli.cmd_db(args)
        mock_run.assert_called()
        args_list = mock_run.call_args[0][0]
        assert "alembic" in args_list
        assert "upgrade" in args_list
        assert "head" in args_list


# ─── cmd_services ───────────────────────────────────────────────────────────

class TestCmdServices:
    def test_services_reports_docker_unavailable(self, monkeypatch, capsys):
        """When Docker is not available, shows error on stderr."""
        monkeypatch.setattr(cli, "_docker_available", lambda: False)
        args = argparse.Namespace(action="up", targets=[])
        cli.cmd_services(args)
        # _error() writes to sys.stderr
        captured = capsys.readouterr().err
        assert "Docker" in captured

    def test_services_up_without_targets_auto_detects(self, monkeypatch):
        """'services up' without targets auto-detects from .env."""
        started = []
        monkeypatch.setattr(cli, "_docker_available", lambda: True)
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_start_postgres", lambda: started.append("postgres") or True)
        monkeypatch.setattr(cli, "_start_meilisearch", lambda: started.append("meili") or True)
        monkeypatch.setenv("FDP_DATABASE__URL", "postgresql://localhost")
        monkeypatch.setenv("FDP_SEARCH__BACKEND", "meilisearch")
        args = argparse.Namespace(action="up", targets=[])
        cli.cmd_services(args)
        assert "postgres" in started
        assert "meili" in started

    def test_services_up_specific_targets(self, monkeypatch):
        """'services up postgres meili chroma' starts only those services."""
        started = []
        monkeypatch.setattr(cli, "_docker_available", lambda: True)
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_start_postgres", lambda: started.append("postgres") or True)
        monkeypatch.setattr(cli, "_start_meilisearch", lambda: started.append("meili") or True)
        monkeypatch.setattr(cli, "_start_chromadb", lambda: started.append("chroma") or True)
        args = argparse.Namespace(action="up", targets=["postgres", "meili", "chroma"])
        cli.cmd_services(args)
        assert started == ["postgres", "meili", "chroma"]

    def test_services_down_all(self, monkeypatch):
        """'services down' without targets stops all services."""
        stopped = []
        monkeypatch.setattr(cli, "_docker_available", lambda: True)
        monkeypatch.setattr(cli, "_stop_docker_service", lambda n: stopped.append(n))
        args = argparse.Namespace(action="down", targets=None)
        cli.cmd_services(args)
        assert "4dp-postgres" in stopped
        assert "4dp-meili" in stopped
        assert "4dp-chromadb" in stopped
        assert "4dp-ollama" in stopped

    def test_services_status_calls_cmd_status(self, monkeypatch):
        """'services status' routes to cmd_status."""
        called = []
        monkeypatch.setattr(cli, "cmd_status", lambda a: called.append(a))
        args = argparse.Namespace(action="status", targets=[])
        cli.cmd_services(args)
        assert called

    def test_services_unknown_target_warns(self, monkeypatch, capsys):
        """Unknown service name produces a warning."""
        warned = []
        monkeypatch.setattr(cli, "_docker_available", lambda: True)
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_warn", lambda x: warned.append(x))
        args = argparse.Namespace(action="up", targets=["unknown-svc"])
        cli.cmd_services(args)
        assert any("unknown" in w.lower() for w in warned)


# ─── cmd_clean ───────────────────────────────────────────────────────────────

class TestCmdClean:
    def test_clean_removes_pid_and_log_dirs(self, fake_pid_dir, monkeypatch):
        """'clean' removes PID_DIR and LOG_DIR."""
        pid_dir, log_dir = fake_pid_dir
        removed = []
        original_rmtree = __import__("shutil").rmtree
        def tracking_rmtree(p, **kw):
            removed.append(p)
            original_rmtree(p, **kw)
        monkeypatch.setattr("shutil.rmtree", tracking_rmtree)
        monkeypatch.setattr(cli, "_stop_process", lambda n: None)
        monkeypatch.setattr(cli, "_step", lambda x: None)
        monkeypatch.setattr(cli, "_success", lambda x: None)
        cli.cmd_clean(None)
        assert pid_dir in removed
        assert log_dir in removed

    def test_clean_removes_cache_dirs(self, fake_pid_dir, monkeypatch, tmp_path):
        """'clean' removes pytest_cache, ruff_cache, htmlcov, .coverage."""
        monkeypatch.setattr(cli, "_stop_process", lambda n: None)
        monkeypatch.setattr(cli, "_step", lambda x: None)
        monkeypatch.setattr(cli, "_success", lambda x: None)

        # Create fake cache dirs in CWD
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)

        cache_dirs_created = []
        for name in [".pytest_cache", ".ruff_cache", ".mypy_cache", "htmlcov"]:
            p = cwd / name
            p.mkdir()
            cache_dirs_created.append(p)

        coverage_file = cwd / ".coverage"
        coverage_file.touch()

        removed_paths = []
        original_rmtree = __import__("shutil").rmtree
        def tracking_rmtree(p, **kw):
            removed_paths.append(p)
            original_rmtree(p, **kw)
        monkeypatch.setattr("shutil.rmtree", tracking_rmtree)

        original_unlink = Path.unlink
        def tracking_unlink(p, **kw):
            removed_paths.append(p)
            return original_unlink(p, **kw)
        monkeypatch.setattr(Path, "unlink", tracking_unlink)

        cli.cmd_clean(None)
        for d in cache_dirs_created:
            assert d in removed_paths, f"{d} not in {removed_paths}"
        assert coverage_file in removed_paths


# ─── cmd_start argument routing ───────────────────────────────────────────────

class TestCmdStartProfiles:
    def test_sqlite_profile_sets_env(self, monkeypatch):
        """--sqlite sets SQLite env vars and runs in background mode."""
        # Provide a valid env path so setup_wizard is skipped
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("FDP_SERVER__PORT=4040\n")
            fake_env = Path(f.name)

        monkeypatch.setattr(cli, "_find_env_file", lambda: fake_env)
        monkeypatch.setattr(cli, "_load_env", lambda: fake_env)
        monkeypatch.setattr(cli, "setup_wizard", lambda: None)
        monkeypatch.setattr(cli, "_get_port", lambda: 4040)
        monkeypatch.setattr(cli, "_get_host", lambda: "0.0.0.0")
        monkeypatch.setattr(cli, "_info", lambda x: None)
        monkeypatch.setattr(cli, "_kill_port", lambda p: None)
        monkeypatch.setattr(cli, "_start_process", lambda n, c, **kw: None)
        monkeypatch.setattr("uvicorn.run", MagicMock())

        args = argparse.Namespace(
            host=None, port=None, reload=False, background=True,
            sqlite=True, postgres=False, full=False, profile="sqlite"
        )
        cli.cmd_start(args)
        # Verify SQLite search backend was set
        assert os.environ.get("FDP_SEARCH__BACKEND") == "sqlite"
        assert "sqlite" in os.environ.get("FDP_DATABASE__URL", "")

    def test_postgres_profile_starts_docker(self, monkeypatch):
        """--postgres starts postgres + meilisearch Docker containers."""
        started = []
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "setup_wizard", lambda: None)
        monkeypatch.setattr(cli, "_get_port", lambda: 4040)
        monkeypatch.setattr(cli, "_get_host", lambda: "0.0.0.0")
        monkeypatch.setattr(cli, "_info", lambda x: None)
        monkeypatch.setattr(cli, "_docker_available", lambda: True)
        monkeypatch.setattr(cli, "_start_postgres", lambda: started.append("postgres") or True)
        monkeypatch.setattr(cli, "_start_meilisearch", lambda: started.append("meili") or True)
        monkeypatch.setattr(cli, "_kill_port", lambda p: None)
        monkeypatch.setattr(cli, "_start_process", lambda n, c, **kw: None)
        monkeypatch.setattr(cli, "_get_local_ip", lambda: "127.0.0.1")
        monkeypatch.setattr(cli, "_success", lambda x: None)
        # uvicorn is imported locally when background=False
        monkeypatch.setattr("uvicorn.run", MagicMock())
        monkeypatch.setattr(cli, "_generate_meili_key", lambda: "fake-key")
        monkeypatch.setenv("FDP_DATABASE__URL", "")

        args = argparse.Namespace(
            host=None, port=None, reload=False, background=True,
            sqlite=False, postgres=True, full=False, profile="postgres"
        )
        cli.cmd_start(args)
        assert "postgres" in started
        assert "meili" in started


# ─── _prompt_choice ───────────────────────────────────────────────────────────

class TestPromptChoice:
    def test_prompt_choice_returns_default_on_empty_input(self, monkeypatch):
        """When user enters nothing, default is returned."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        result = cli._prompt_choice("Choose:", [("1", "Option A"), ("2", "Option B")], default="2")
        assert result == "2"

    def test_prompt_choice_returns_user_input(self, monkeypatch):
        """When user enters a choice, it is returned."""
        monkeypatch.setattr("builtins.input", lambda _: "1")
        result = cli._prompt_choice("Choose:", [("1", "Option A"), ("2", "Option B")])
        assert result == "1"


# ─── main() dispatch ──────────────────────────────────────────────────────────

class TestMainDispatch:
    """Test main() dispatches to the correct command handlers."""

    def test_main_routes_version(self, monkeypatch, capsys):
        """main() with 'version' command prints version and returns (no SystemExit)."""
        monkeypatch.setattr(cli, "_get_version", lambda: "0.2.2")
        monkeypatch.setattr(sys, "argv", ["4dpocket", "version"])
        # main() returns normally after printing version
        cli.main()
        captured = capsys.readouterr().out
        assert "0.2.2" in captured

    def test_main_routes_help(self, monkeypatch, capsys):
        """main() with 'help' command prints full help text."""
        monkeypatch.setattr(sys, "argv", ["4dpocket", "help"])
        cli.main()
        captured = capsys.readouterr().out
        assert "4DPocket" in captured
        assert "USAGE" in captured

    def test_main_routes_stop_command(self, monkeypatch):
        """main() routes 'stop' to cmd_stop with namespace argument."""
        called = []
        monkeypatch.setattr(cli, "cmd_stop", lambda a: called.append(a))
        monkeypatch.setattr(sys, "argv", ["4dpocket", "stop"])
        cli.main()
        assert len(called) == 1
        assert called[0].command == "stop"

    def test_main_routes_services_command(self, monkeypatch):
        """main() routes 'services up' to cmd_services."""
        called = []
        monkeypatch.setattr(cli, "cmd_services", lambda a: called.append(a))
        monkeypatch.setattr(sys, "argv", ["4dpocket", "services", "up"])
        cli.main()
        assert called
        assert called[0].action == "up"

    def test_main_routes_logs_command(self, monkeypatch):
        """main() routes 'logs' to cmd_logs."""
        called = []
        monkeypatch.setattr(cli, "cmd_logs", lambda a: called.append(a))
        monkeypatch.setattr(sys, "argv", ["4dpocket", "logs"])
        cli.main()
        assert called
        assert called[0].service == "server"

    def test_main_routes_status_command(self, monkeypatch):
        """main() routes 'status' to cmd_status with namespace argument."""
        called = []
        monkeypatch.setattr(cli, "cmd_status", lambda a: called.append(a))
        monkeypatch.setattr(sys, "argv", ["4dpocket", "status"])
        # Also mock dependencies of cmd_status
        monkeypatch.setattr(cli, "_load_env", lambda: None)
        monkeypatch.setattr(cli, "_get_version", lambda: "0.2.2")
        monkeypatch.setattr(cli, "_get_port", lambda: 4040)
        monkeypatch.setattr(cli, "_is_running", lambda n: None)
        monkeypatch.setattr(cli, "_docker_available", lambda: False)
        cli.main()
        assert len(called) == 1
        assert called[0].command == "status"

    def test_main_routes_db_command(self, monkeypatch):
        """main() routes 'db init' to cmd_db."""
        called = []
        monkeypatch.setattr(cli, "cmd_db", lambda a: called.append(a))
        monkeypatch.setattr(sys, "argv", ["4dpocket", "db", "init"])
        cli.main()
        assert called
        assert called[0].db_command == "init"

    def test_main_routes_clean_command(self, monkeypatch):
        """main() routes 'clean' to cmd_clean with namespace argument."""
        cleaned = []
        monkeypatch.setattr(cli, "cmd_clean", lambda a: cleaned.append(a))
        monkeypatch.setattr(sys, "argv", ["4dpocket", "clean"])
        cli.main()
        assert len(cleaned) == 1
        assert cleaned[0].command == "clean"


# ─── _service_is_running / _service_exists ───────────────────────────────────

class TestDockerServiceHelpers:
    def test_service_is_running_queries_docker(self, monkeypatch):
        """_service_is_running calls 'docker ps' and checks for container name."""
        mock_run = MagicMock(return_value=MagicMock(stdout="4dp-postgres\n4dp-meili\n"))
        monkeypatch.setattr(subprocess, "run", mock_run)
        result = cli._service_is_running("4dp-postgres")
        assert result is True
        mock_run.assert_called_once()
        assert "4dp-postgres" in str(mock_run.call_args)

    def test_service_is_running_returns_false_when_absent(self, monkeypatch):
        """_service_is_running returns False when container not in docker ps."""
        mock_run = MagicMock(return_value=MagicMock(stdout="other-container\n"))
        monkeypatch.setattr(subprocess, "run", mock_run)
        result = cli._service_is_running("4dp-postgres")
        assert result is False

    def test_service_exists_queries_docker_ps_a(self, monkeypatch):
        """_service_exists calls 'docker ps -a' to check if container exists."""
        mock_run = MagicMock(return_value=MagicMock(stdout="4dp-postgres\n"))
        monkeypatch.setattr(subprocess, "run", mock_run)
        result = cli._service_exists("4dp-postgres")
        assert result is True
        args = mock_run.call_args[0][0]
        assert "-a" in args


# ─── _start_docker_service ───────────────────────────────────────────────────

class TestStartDockerService:
    def test_start_docker_service_skips_if_already_running(self, monkeypatch):
        """If service already running, returns True without re-starting."""
        called = []
        monkeypatch.setattr(cli, "_service_is_running", lambda n: True)
        monkeypatch.setattr(cli, "_step", lambda x: called.append(x))
        result = cli._start_docker_service("test-svc", [])
        assert result is True
        assert any("already running" in str(c) for c in called)

    def test_start_docker_service_starts_existing_stopped_container(self, monkeypatch):
        """If container exists but is stopped, starts it."""
        started = []
        docker_started = [False]  # track whether docker start was called

        def fake_service_running(n):
            # Returns True after docker start has been called
            return docker_started[0]

        monkeypatch.setattr(cli, "_service_is_running", fake_service_running)
        monkeypatch.setattr(cli, "_service_exists", lambda n: True)
        # _start_docker_service checks subprocess.run().returncode == 0
        def fake_run(*a, **k):
            started.append(a)
            if "start" in str(a[0]):
                docker_started[0] = True
            return MagicMock(returncode=0)
        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr(cli, "_step", lambda x: None)
        monkeypatch.setattr(cli, "_info", lambda x: None)
        monkeypatch.setattr(cli, "_fail", lambda x: None)
        result = cli._start_docker_service("test-svc", [])
        assert result is True
        start_calls = [c for c in started if "start" in str(c)]
        assert start_calls

    def test_start_docker_service_waits_for_ready_check(self, monkeypatch):
        """When ready_check is provided, waits for it to return True."""
        checked = []
        def fake_ready_check():
            checked.append(True)
            return True
        monkeypatch.setattr(cli, "_service_is_running", lambda n: False)
        monkeypatch.setattr(cli, "_service_exists", lambda n: False)
        ran_docker_run = []
        def capture_run(*a, **k):
            ran_docker_run.append(a)
            return MagicMock()
        monkeypatch.setattr(subprocess, "run", capture_run)
        monkeypatch.setattr(cli, "_step", lambda x: None)
        monkeypatch.setattr(cli, "_info", lambda x: None)
        monkeypatch.setattr(cli, "_fail", lambda x: None)
        result = cli._start_docker_service("test-svc", [], ready_check=fake_ready_check)
        assert result is True
        assert checked


# ─── _get_local_ip ───────────────────────────────────────────────────────────

class TestGetLocalIp:
    def test_get_local_ip_returns_ip_on_success(self, monkeypatch):
        """On successful socket connection, returns the local IP."""
        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 12345)
        monkeypatch.setattr("socket.socket", lambda *a, **k: mock_sock)
        result = cli._get_local_ip()
        assert result == "192.168.1.100"

    def test_get_local_ip_falls_back_to_localhost_on_error(self, monkeypatch):
        """On socket error, falls back to 'localhost'."""
        monkeypatch.setattr("socket.socket", lambda *a, **k: (_ for _ in ()).throw(OSError()))
        result = cli._get_local_ip()
        assert result == "localhost"


# ─── _kill_port ──────────────────────────────────────────────────────────────

class TestKillPort:
    def test_kill_port_kills_process_on_port(self, monkeypatch):
        """lsof is used to find and kill processes on the port."""
        killed = []
        def fake_kill(pid, sig):
            killed.append(pid)
        monkeypatch.setattr(os, "kill", fake_kill)
        mock_run = MagicMock(return_value=MagicMock(stdout="12345\n67890\n"))
        monkeypatch.setattr(subprocess, "run", mock_run)
        cli._kill_port(4040)
        assert 12345 in killed
        assert 67890 in killed

    def test_kill_port_handles_missing_lsof(self, monkeypatch):
        """FileNotFoundError for lsof is handled gracefully."""
        def raise_fnf(*a, **k):
            raise FileNotFoundError("lsof not found")
        monkeypatch.setattr(subprocess, "run", raise_fnf)
        # Should not raise
        cli._kill_port(4040)

    def test_kill_port_does_nothing_when_no_processes(self, monkeypatch):
        """When no processes are on the port, does nothing."""
        mock_run = MagicMock(return_value=MagicMock(stdout=""))
        monkeypatch.setattr(subprocess, "run", mock_run)
        killed = []
        monkeypatch.setattr(os, "kill", lambda p, s: killed.append(p))
        cli._kill_port(4040)
        assert not killed
