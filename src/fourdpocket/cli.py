"""4DPocket CLI — full-featured entry point with app.sh parity."""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

APP_NAME = "4DPocket"
DEFAULT_DATA_DIR = Path.home() / ".4dpocket"
PID_DIR = DEFAULT_DATA_DIR / "run"
LOG_DIR = DEFAULT_DATA_DIR / "logs"

# Docker container names (same as app.sh)
POSTGRES_CONTAINER = "4dp-postgres"
MEILI_CONTAINER = "4dp-meili"
CHROMA_CONTAINER = "4dp-chromadb"
OLLAMA_CONTAINER = "4dp-ollama"

# Default PostgreSQL credentials
PG_USER = os.environ.get("PG_USER", "4dp")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "4dp")
PG_DB = os.environ.get("PG_DB", "4dpocket")
PG_PORT = os.environ.get("PG_PORT", "5432")


# ─── Colors ──────────────────────────────────────────────────────

class _C:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    NC = "\033[0m"


def _info(msg):
    print(f"{_C.CYAN}==> {msg}{_C.NC}")


def _success(msg):
    print(f"{_C.GREEN}==> {msg}{_C.NC}")


def _warn(msg):
    print(f"{_C.YELLOW}==> {msg}{_C.NC}")


def _error(msg):
    print(f"{_C.RED}==> ERROR: {msg}{_C.NC}", file=sys.stderr)


def _step(msg):
    print(f"  {_C.GREEN}✓{_C.NC} {msg}")


def _fail(msg):
    print(f"  {_C.RED}✗{_C.NC} {msg}")


# ─── Helpers ─────────────────────────────────────────────────────

def _get_version():
    from fourdpocket import __version__
    return __version__


def _find_env_file():
    """Find .env file. Priority: CWD > ~/.4dpocket/."""
    cwd_env = Path.cwd() / ".env"
    if cwd_env.is_file():
        return cwd_env
    home_env = DEFAULT_DATA_DIR / ".env"
    if home_env.is_file():
        return home_env
    return None


def _load_env():
    """Load .env file into os.environ."""
    env_path = _find_env_file()
    if env_path:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip()
                if key not in os.environ:
                    os.environ[key] = value
    return env_path


def _get_port():
    return int(os.environ.get("FDP_SERVER__PORT", "4040"))


def _get_host():
    return os.environ.get("FDP_SERVER__HOST", "0.0.0.0")


def _get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def _prompt_choice(label, options, default="1"):
    print(f"  {label}")
    for num, desc in options:
        print(f"    {num}) {desc}")
    choice = input(f"\n  Choose [{default}]: ").strip() or default
    print()
    return choice


def _has_command(cmd):
    from shutil import which
    return which(cmd) is not None


# ─── PID Management ─────────────────────────────────────────────

def _pid_file(name):
    return PID_DIR / f"{name}.pid"


def _log_file(name):
    return LOG_DIR / f"{name}.log"


def _is_running(name):
    pf = _pid_file(name)
    if pf.exists():
        pid = int(pf.read_text().strip())
        try:
            os.kill(pid, 0)
            return pid
        except OSError:
            pf.unlink(missing_ok=True)
    return None


def _start_process(name, cmd, cwd=None):
    """Start a background process, track with PID file."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    pid = _is_running(name)
    if pid:
        _warn(f"{name} already running (PID: {pid})")
        return pid

    log = _log_file(name)
    with open(log, "a") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, cwd=cwd)

    _pid_file(name).write_text(str(proc.pid))
    time.sleep(2)

    if proc.poll() is None:
        _step(f"{name} started (PID: {proc.pid})")
        return proc.pid
    else:
        _fail(f"{name} failed to start. Check: tail -f {log}")
        _pid_file(name).unlink(missing_ok=True)
        return None


def _stop_process(name):
    """Stop a background process by PID file."""
    pf = _pid_file(name)
    if not pf.exists():
        return

    pid = int(pf.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except OSError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
        _step(f"{name} stopped (was PID: {pid})")
    except OSError:
        pass
    pf.unlink(missing_ok=True)


def _kill_port(port):
    """Kill any process on the given port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"], capture_output=True, text=True
        )
        if result.stdout.strip():
            for pid in result.stdout.strip().split("\n"):
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except OSError:
                    pass
            time.sleep(1)
    except FileNotFoundError:
        pass


# ─── Docker Service Management ──────────────────────────────────

def _docker_available():
    if not _has_command("docker"):
        return False
    return subprocess.run(
        ["docker", "info"], capture_output=True
    ).returncode == 0


def _service_is_running(name):
    r = subprocess.run(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    return name in r.stdout


def _service_exists(name):
    r = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    return name in r.stdout


def _start_docker_service(name, run_args, ready_check=None, timeout=30):
    """Start a Docker container, wait for ready."""
    if _service_is_running(name):
        _step(f"{name} already running")
        return True

    label = name.replace("4dp-", "").capitalize()
    _info(f"Starting {label}...")

    if _service_exists(name):
        subprocess.run(["docker", "start", name], capture_output=True)
    else:
        subprocess.run(
            ["docker", "run", "-d", "--name", name, *run_args],
            capture_output=True,
        )

    if ready_check:
        for _ in range(timeout):
            if ready_check():
                _step(f"{label} ready")
                return True
            time.sleep(1)
        _fail(f"{label} failed to start within {timeout}s")
        return False

    time.sleep(3)
    if _service_is_running(name):
        _step(f"{label} ready")
        return True
    _fail(f"{label} failed to start")
    return False


def _stop_docker_service(name):
    if _service_is_running(name):
        subprocess.run(["docker", "stop", name], capture_output=True)
        _step(f"{name} stopped")
    else:
        print(f"  {_C.DIM}○{_C.NC} {name} (not running)")


def _start_postgres():
    def ready():
        r = subprocess.run(
            ["docker", "exec", POSTGRES_CONTAINER, "pg_isready", "-U", PG_USER, "-d", PG_DB],
            capture_output=True,
        )
        return r.returncode == 0

    return _start_docker_service(POSTGRES_CONTAINER, [
        "-p", f"{PG_PORT}:5432",
        "-e", f"POSTGRES_USER={PG_USER}",
        "-e", f"POSTGRES_PASSWORD={PG_PASSWORD}",
        "-e", f"POSTGRES_DB={PG_DB}",
        "-v", "4dp-postgres:/var/lib/postgresql/data",
        "postgres:16-alpine",
    ], ready_check=ready)


def _generate_meili_key():
    """Get or generate a Meilisearch master key."""
    import secrets
    key_file = DEFAULT_DATA_DIR / "meili_master_key"
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_urlsafe(24)
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    key_file.write_text(key)
    key_file.chmod(0o600)
    return key


def _start_meilisearch():
    meili_key = os.environ.get("FDP_SEARCH__MEILI_MASTER_KEY") or _generate_meili_key()

    def ready():
        try:
            import httpx
            return httpx.get("http://localhost:7700/health", timeout=2).status_code == 200
        except Exception:
            return False

    return _start_docker_service(MEILI_CONTAINER, [
        "-p", "7700:7700",
        "-e", f"MEILI_MASTER_KEY={meili_key}",
        "-v", "4dp-meili:/meili_data",
        "getmeili/meilisearch:v1.12",
    ], ready_check=ready)


def _start_chromadb():
    return _start_docker_service(CHROMA_CONTAINER, [
        "-p", "8000:8000",
        "-v", "4dp-chroma:/chroma/chroma",
        "chromadb/chroma:latest",
    ])


def _start_ollama():
    # Prefer native Ollama if running
    if _has_command("ollama"):
        try:
            import httpx
            if httpx.get("http://localhost:11434/api/tags", timeout=2).status_code == 200:
                _step("Ollama running natively (skipping Docker)")
                return True
        except Exception:
            pass

    return _start_docker_service(OLLAMA_CONTAINER, [
        "-p", "11434:11434",
        "-v", "4dp-ollama:/root/.ollama",
        "ollama/ollama:latest",
    ])


# ─── Setup Wizard ────────────────────────────────────────────────

def setup_wizard():
    """Interactive first-run configuration wizard."""
    print()
    print(f"  {_C.BOLD}{_C.CYAN}{APP_NAME} — Setup{_C.NC}")
    print("  " + "─" * 40)
    print()

    config = {}
    data_dir = DEFAULT_DATA_DIR / "data"

    # ── Database
    choice = _prompt_choice("Database:", [
        ("1", "SQLite        (zero-config, recommended for personal use)"),
        ("2", "PostgreSQL    (for larger deployments)"),
    ])

    if choice == "2":
        default_pg = f"postgresql://{PG_USER}:{PG_PASSWORD}@localhost:{PG_PORT}/{PG_DB}"
        pg_url = input(f"  PostgreSQL URL [{default_pg}]: ").strip() or default_pg
        config["FDP_DATABASE__URL"] = pg_url
        config["FDP_SEARCH__BACKEND"] = "meilisearch"
        meili = input("  Meilisearch URL [http://localhost:7700]: ").strip() or "http://localhost:7700"
        config["FDP_SEARCH__MEILI_URL"] = meili
        meili_key = input("  Meilisearch master key (optional): ").strip()
        if meili_key:
            config["FDP_SEARCH__MEILI_MASTER_KEY"] = meili_key
        print()
        print("  NOTE: Install PostgreSQL support with: pip install 4dpocket[postgres]")
        print()
    else:
        config["FDP_DATABASE__URL"] = f"sqlite:///{data_dir}/4dpocket.db"
        config["FDP_SEARCH__BACKEND"] = "sqlite"

    # ── AI Provider
    choice = _prompt_choice("AI provider:", [
        ("1", "Ollama        (local, free — requires Ollama running)"),
        ("2", "Groq          (cloud, fast — requires API key)"),
        ("3", "NVIDIA        (cloud — requires API key)"),
        ("4", "Custom        (any OpenAI/Anthropic-compatible endpoint)"),
        ("5", "None          (disable AI features)"),
    ])

    providers = {"1": "ollama", "2": "groq", "3": "nvidia", "4": "custom"}
    provider = providers.get(choice)

    if provider == "ollama":
        config["FDP_AI__CHAT_PROVIDER"] = "ollama"
        url = input("  Ollama URL [http://localhost:11434]: ").strip() or "http://localhost:11434"
        config["FDP_AI__OLLAMA_URL"] = url
        model = input("  Ollama model [llama3.2]: ").strip() or "llama3.2"
        config["FDP_AI__OLLAMA_MODEL"] = model
        print()
    elif provider == "groq":
        config["FDP_AI__CHAT_PROVIDER"] = "groq"
        key = input("  Groq API key: ").strip()
        if key:
            config["FDP_AI__GROQ_API_KEY"] = key
        print()
    elif provider == "nvidia":
        config["FDP_AI__CHAT_PROVIDER"] = "nvidia"
        key = input("  NVIDIA API key: ").strip()
        if key:
            config["FDP_AI__NVIDIA_API_KEY"] = key
        print()
    elif provider == "custom":
        config["FDP_AI__CHAT_PROVIDER"] = "custom"
        config["FDP_AI__CUSTOM_BASE_URL"] = input("  API base URL: ").strip()
        config["FDP_AI__CUSTOM_API_KEY"] = input("  API key: ").strip()
        config["FDP_AI__CUSTOM_MODEL"] = input("  Model name: ").strip()
        api_type = input("  API type (openai/anthropic) [openai]: ").strip() or "openai"
        config["FDP_AI__CUSTOM_API_TYPE"] = api_type
        print()

    # ── Auth
    choice = _prompt_choice("Authentication:", [
        ("1", "Single user   (no login required)"),
        ("2", "Multi-user    (email/password registration)"),
    ])
    config["FDP_AUTH__MODE"] = "multi" if choice == "2" else "single"

    # ── Server
    port = input("  Server port [4040]: ").strip() or "4040"
    config["FDP_SERVER__PORT"] = port
    print()

    # ── Defaults
    config["FDP_STORAGE__BASE_PATH"] = str(data_dir)
    config["FDP_AI__AUTO_TAG"] = "true"
    config["FDP_AI__AUTO_SUMMARIZE"] = "true"
    config["FDP_AI__SYNC_ENRICHMENT"] = "true"
    config["FDP_SERVER__HOST"] = "0.0.0.0"
    config["FDP_SERVER__CORS_ORIGINS"] = f'["http://localhost:{port}"]'
    config["FDP_AI__EMBEDDING_PROVIDER"] = "local"
    config["FDP_AI__EMBEDDING_MODEL"] = "all-MiniLM-L6-v2"

    # ── Write config
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    env_path = DEFAULT_DATA_DIR / ".env"
    lines = [
        "# 4DPocket Configuration",
        "# Generated by: 4dpocket setup",
        "# Edit this file to change settings, or re-run: 4dpocket setup",
        "",
    ]
    for key, value in config.items():
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n")

    _success("Setup complete!")
    print(f"  Config:    {env_path}")
    print(f"  Data dir:  {data_dir}")
    print()
    print(f"  Quick start:       {_C.YELLOW}4dpocket start{_C.NC}")
    print(f"  With PostgreSQL:   {_C.YELLOW}4dpocket start --postgres{_C.NC}")
    print(f"  Full stack:        {_C.YELLOW}4dpocket start --full{_C.NC}")
    print()
    return env_path


# ─── Commands ────────────────────────────────────────────────────

def cmd_setup(_args):
    setup_wizard()


def cmd_start(args):
    """Start the 4DPocket server."""
    env_path = _load_env()
    if env_path is None:
        print("\n  No configuration found. Running setup wizard...\n")
        env_path = setup_wizard()
        _load_env()

    port = _get_port()
    host = _get_host()

    # Apply profile overrides
    profile = getattr(args, "profile", None)
    if profile == "sqlite" or args.sqlite:
        data_dir = DEFAULT_DATA_DIR / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        os.environ["FDP_DATABASE__URL"] = f"sqlite:///{data_dir}/4dpocket.db"
        os.environ["FDP_SEARCH__BACKEND"] = "sqlite"
        _info("Profile: SQLite (zero-config)")
    elif profile == "postgres" or args.postgres:
        if _docker_available():
            _start_postgres()
            _start_meilisearch()
        db_url = os.environ.get(
            "FDP_DATABASE__URL",
            f"postgresql://{PG_USER}:{PG_PASSWORD}@localhost:{PG_PORT}/{PG_DB}",
        )
        os.environ["FDP_DATABASE__URL"] = db_url
        os.environ.setdefault("FDP_SEARCH__BACKEND", "meilisearch")
        os.environ.setdefault("FDP_SEARCH__MEILI_URL", "http://localhost:7700")
        os.environ.setdefault("FDP_SEARCH__MEILI_MASTER_KEY", _generate_meili_key())
        _info("Profile: PostgreSQL + Meilisearch")
    elif profile == "full" or args.full:
        if _docker_available():
            _start_postgres()
            _start_meilisearch()
            _start_chromadb()
            _start_ollama()
        db_url = os.environ.get(
            "FDP_DATABASE__URL",
            f"postgresql://{PG_USER}:{PG_PASSWORD}@localhost:{PG_PORT}/{PG_DB}",
        )
        os.environ["FDP_DATABASE__URL"] = db_url
        os.environ.setdefault("FDP_SEARCH__BACKEND", "meilisearch")
        os.environ.setdefault("FDP_SEARCH__MEILI_URL", "http://localhost:7700")
        os.environ.setdefault("FDP_SEARCH__MEILI_MASTER_KEY", _generate_meili_key())
        os.environ["FDP_AI__CHAT_PROVIDER"] = "ollama"
        os.environ["FDP_AI__OLLAMA_URL"] = "http://localhost:11434"
        _info("Profile: Full stack (PostgreSQL + Meilisearch + ChromaDB + Ollama)")
    else:
        # Auto-start Docker services based on .env
        db_url = os.environ.get("FDP_DATABASE__URL", "")
        if db_url.startswith("postgresql") and _docker_available():
            _start_postgres()
        if os.environ.get("FDP_SEARCH__BACKEND") == "meilisearch" and _docker_available():
            _start_meilisearch()

    # Override host/port from CLI args
    if args.host:
        host = args.host
    if args.port:
        port = args.port

    print()

    if args.background:
        _kill_port(port)
        _start_process("server", [
            sys.executable, "-m", "uvicorn", "fourdpocket.main:app",
            "--host", host, "--port", str(port), "--log-level", "info",
        ])

        local_ip = _get_local_ip()
        print()
        _success(f"{APP_NAME} is running!")
        print()
        print(f"  {_C.BOLD}App:{_C.NC}       http://localhost:{port}")
        print(f"  {_C.BOLD}API Docs:{_C.NC}  http://localhost:{port}/docs")
        print(f"  {_C.BOLD}Network:{_C.NC}   http://{local_ip}:{port}")
        print()
        print(f"  {_C.DIM}Logs:    4dpocket logs{_C.NC}")
        print(f"  {_C.DIM}Status:  4dpocket status{_C.NC}")
        print(f"  {_C.DIM}Stop:    4dpocket stop{_C.NC}")
    else:
        print(f"  Starting {APP_NAME} on http://localhost:{port}")
        print(f"  {_C.DIM}Press Ctrl+C to stop{_C.NC}")
        print()
        import uvicorn
        uvicorn.run(
            "fourdpocket.main:app",
            host=host,
            port=port,
            reload=args.reload,
            log_level="info",
        )


def cmd_stop(_args):
    """Stop running services."""
    _info("Stopping services...")
    _stop_process("server")
    _success("Services stopped.")


def cmd_restart(args):
    """Restart services."""
    _info("Restarting services...")
    _stop_process("server")
    time.sleep(1)
    args.background = True
    cmd_start(args)


def cmd_status(_args):
    """Show service status."""
    _load_env()
    port = _get_port()
    version = _get_version()

    print(f"{_C.BOLD}{APP_NAME} v{version}{_C.NC}")
    print()

    # Application
    print(f"{_C.BOLD}Application:{_C.NC}")
    pid = _is_running("server")
    if pid:
        print(f"  {_C.GREEN}●{_C.NC} Server     PID: {pid}  Port: {port}")
    else:
        # Check if something is on the port anyway (foreground mode)
        try:
            import httpx
            r = httpx.get(f"http://localhost:{port}/api/v1/health", timeout=2)
            if r.status_code == 200:
                print(f"  {_C.GREEN}●{_C.NC} Server     Port: {port} (foreground)")
            else:
                print(f"  {_C.RED}●{_C.NC} Server     not running")
        except Exception:
            print(f"  {_C.RED}●{_C.NC} Server     not running")

    print()

    # Docker services
    if _docker_available():
        print(f"{_C.BOLD}Docker Services:{_C.NC}")
        for name, label in [
            (POSTGRES_CONTAINER, "PostgreSQL"),
            (MEILI_CONTAINER, "Meilisearch"),
            (CHROMA_CONTAINER, "ChromaDB"),
            (OLLAMA_CONTAINER, "Ollama"),
        ]:
            if _service_is_running(name):
                r = subprocess.run(
                    ["docker", "port", name], capture_output=True, text=True,
                )
                port_info = r.stdout.strip().split("\n")[0].split(":")[-1] if r.stdout.strip() else "?"
                print(f"  {_C.GREEN}●{_C.NC} {label:<14} {_C.DIM}({name}, port: {port_info}){_C.NC}")
            elif _service_exists(name):
                print(f"  {_C.YELLOW}●{_C.NC} {label:<14} {_C.DIM}({name}, stopped){_C.NC}")
            else:
                print(f"  {_C.DIM}○{_C.NC} {label:<14} {_C.DIM}(not created){_C.NC}")
        print()

    # Configuration
    print(f"{_C.BOLD}Configuration:{_C.NC}")
    env_path = _find_env_file()
    db_url = os.environ.get("FDP_DATABASE__URL", "sqlite:///./data/4dpocket.db")
    print(f"  Config:   {env_path or 'none (using defaults)'}")
    print(f"  Data:     {os.environ.get('FDP_STORAGE__BASE_PATH', './data')}")
    print(f"  Database: {'PostgreSQL' if db_url.startswith('postgresql') else 'SQLite'}")
    print(f"  Search:   {os.environ.get('FDP_SEARCH__BACKEND', 'sqlite')}")
    print(f"  AI:       {os.environ.get('FDP_AI__CHAT_PROVIDER', 'ollama')}")
    print(f"  Auth:     {os.environ.get('FDP_AUTH__MODE', 'single')}")


def cmd_logs(args):
    """Tail service logs."""
    log = _log_file(args.service)
    if not log.exists():
        _warn(f"No log file at {log}")
        return
    try:
        subprocess.run(["tail", "-f", str(log)])
    except KeyboardInterrupt:
        pass


def cmd_db(args):
    """Database management."""
    _load_env()
    db_url = os.environ.get("FDP_DATABASE__URL", "sqlite:///./data/4dpocket.db")

    if args.db_command == "init":
        _info("Initializing database...")
        from fourdpocket.db.session import init_db
        init_db()
        _success("Database tables created.")

    elif args.db_command == "reset":
        _warn("This will DESTROY ALL DATA in the database.")

        # Safety: refuse to drop while server or worker are running.
        if not args.yes:
            running = []
            for svc_name in ("server", "worker"):
                if _is_running(svc_name):
                    running.append(svc_name)
            if running:
                _error(
                    f"The following service(s) are still running: {', '.join(running)}. "
                    "Stop them first (4dpocket stop) or pass --yes to override."
                )
                return

            confirm = input("  Type 'yes' to confirm: ").strip()
            if confirm != "yes":
                print("  Cancelled.")
                return

        # Clear any cached engine before dropping so SQLite file locks are released.
        from fourdpocket.db.session import reset_engine
        reset_engine()

        if db_url.startswith("postgresql"):
            _info("Resetting PostgreSQL database...")
            db_name = db_url.rsplit("/", 1)[-1]
            base_url = db_url.rsplit("/", 1)[0] + "/postgres"
            # Use --set to pass db_name as a psql variable to avoid SQL injection
            subprocess.run(["psql", base_url,
                "--set", f"dbname={db_name}",
                "-c", "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                      "WHERE datname = :'dbname' AND pid <> pg_backend_pid();"],
                capture_output=True)
            subprocess.run(["psql", base_url,
                "--set", f"dbname={db_name}",
                "-c", 'DROP DATABASE IF EXISTS :"dbname";'])
            subprocess.run(["psql", base_url,
                "--set", f"dbname={db_name}",
                "--set", f"owner={PG_USER}",
                "-c", 'CREATE DATABASE :"dbname" OWNER :"owner";'])
        else:
            db_path = db_url.replace("sqlite:///", "")
            _info(f"Resetting SQLite database: {db_path}...")
            for suffix in ["", "-journal", "-shm", "-wal"]:
                Path(db_path + suffix).unlink(missing_ok=True)

        from fourdpocket.db.session import init_db, reset_engine
        reset_engine()  # clear cached connection after drop
        init_db()
        _success("Database reset and reinitialized.")

    elif args.db_command == "migrate":
        _info("Running Alembic migrations...")
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"])
        _success("Migrations applied.")

    elif args.db_command == "shell":
        if db_url.startswith("postgresql"):
            _info("Opening PostgreSQL shell...")
            os.execvp("psql", ["psql", db_url])
        else:
            db_path = db_url.replace("sqlite:///", "")
            if not Path(db_path).exists():
                _warn(f"Database file not found: {db_path}")
                _warn("Run '4dpocket db init' first.")
                return
            _info("Opening SQLite shell...")
            os.execvp("sqlite3", ["sqlite3", db_path])

    elif args.db_command == "backup":
        from fourdpocket.config import get_settings
        from fourdpocket.ops.backup import run_backup

        settings = get_settings()
        out = Path(args.out) if args.out else (
            Path("./data/backups") /
            f"4dpocket-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.tar.gz"
        )
        _info(f"Backing up to: {out}")
        db_url_resolved = os.environ.get("FDP_DATABASE__URL", db_url)
        vec = settings.search.vector_backend
        if vec == "auto":
            vec = "pgvector" if db_url_resolved.startswith("postgresql") else "chroma"
        run_backup(
            db_url=db_url_resolved,
            storage_base=settings.storage.base_path,
            out_path=out,
            vector_backend=vec,
        )

    elif args.db_command == "restore":
        from fourdpocket.config import get_settings
        from fourdpocket.ops.restore import run_restore

        settings = get_settings()
        if not args.from_path:
            _error("--from PATH is required for restore.")
            sys.exit(1)
        backup_dir = Path("./data/backups")
        _info(f"Restoring from: {args.from_path}")
        run_restore(
            archive_path=Path(args.from_path),
            db_url=os.environ.get("FDP_DATABASE__URL", db_url),
            storage_base=settings.storage.base_path,
            backup_dir=backup_dir,
            force=args.force,
        )

    else:
        print("Usage: 4dpocket db <init|reset|migrate|shell|backup|restore>")


def cmd_embed(args):
    """Embedding management."""
    _load_env()

    if args.embed_command == "reindex":
        from fourdpocket.config import get_settings
        from fourdpocket.db.session import get_engine
        from fourdpocket.ops.reembed import run_reembed

        settings = get_settings()
        db_url = os.environ.get("FDP_DATABASE__URL", "sqlite:///./data/4dpocket.db")
        vec = settings.search.vector_backend
        if vec == "auto":
            vec = "pgvector" if db_url.startswith("postgresql") else "chroma"

        _info("Re-indexing embeddings...")
        run_reembed(
            engine=get_engine(),
            user_email=getattr(args, "user", None),
            dry_run=args.dry_run,
            vector_backend=vec,
        )
        if not args.dry_run:
            _success("Re-embedding tasks enqueued.")
    else:
        print("Usage: 4dpocket embed <reindex>")


def cmd_auth(args):
    """Auth management."""
    _load_env()

    if args.auth_command == "rotate-key":
        from fourdpocket.ops.rotate_key import _resolve_key_dir, run_rotate_key

        key_dir = _resolve_key_dir()
        _info(f"Rotating secret key in: {key_dir}")
        run_rotate_key(key_dir=key_dir, grace_days=args.grace_days)
    else:
        print("Usage: 4dpocket auth <rotate-key>")


def cmd_services(args):
    """Docker service management."""
    action = args.action

    # `status` is Docker-agnostic (it prints general app status); route early
    # so it works on machines without Docker installed.
    if action == "status":
        cmd_status(args)
        return

    if not _docker_available():
        _error("Docker is required but not installed or not running.")
        return

    if action == "up":
        targets = args.targets or []
        if not targets:
            # Auto-detect from .env
            _load_env()
            db_url = os.environ.get("FDP_DATABASE__URL", "")
            if db_url.startswith("postgresql"):
                _start_postgres()
            if os.environ.get("FDP_SEARCH__BACKEND") == "meilisearch":
                _start_meilisearch()
            if os.environ.get("FDP_AI__CHAT_PROVIDER") == "ollama":
                _start_ollama()
            return

        for svc in targets:
            if svc in ("postgres", "pg", "postgresql"):
                _start_postgres()
            elif svc in ("meilisearch", "meili"):
                _start_meilisearch()
            elif svc in ("chromadb", "chroma"):
                _start_chromadb()
            elif svc in ("ollama",):
                _start_ollama()
            elif svc == "all":
                _start_postgres()
                _start_meilisearch()
                _start_chromadb()
                _start_ollama()
            else:
                _warn(f"Unknown service: {svc} (use: postgres, meilisearch, chromadb, ollama, all)")

    elif action == "down":
        targets = args.targets or ["all"]
        for svc in targets:
            if svc in ("postgres", "pg", "postgresql"):
                _stop_docker_service(POSTGRES_CONTAINER)
            elif svc in ("meilisearch", "meili"):
                _stop_docker_service(MEILI_CONTAINER)
            elif svc in ("chromadb", "chroma"):
                _stop_docker_service(CHROMA_CONTAINER)
            elif svc in ("ollama",):
                _stop_docker_service(OLLAMA_CONTAINER)
            elif svc == "all":
                _stop_docker_service(POSTGRES_CONTAINER)
                _stop_docker_service(MEILI_CONTAINER)
                _stop_docker_service(CHROMA_CONTAINER)
                _stop_docker_service(OLLAMA_CONTAINER)

    else:
        print("Usage: 4dpocket services <up|down|status> [service...]")


def cmd_clean(_args):
    """Clean up logs, PID files, and caches."""
    _info("Cleaning up...")
    _stop_process("server")

    import shutil
    for d in [PID_DIR, LOG_DIR]:
        if d.exists():
            shutil.rmtree(d)
    _step("Removed PID files and logs")

    # Clean Python caches
    cache_dirs = [
        Path.cwd() / ".pytest_cache",
        Path.cwd() / ".ruff_cache",
        Path.cwd() / ".mypy_cache",
        Path.cwd() / "htmlcov",
    ]
    for d in cache_dirs:
        if d.exists():
            shutil.rmtree(d)
    coverage = Path.cwd() / ".coverage"
    if coverage.exists():
        coverage.unlink()

    _success("Clean complete.")


# ─── Help ────────────────────────────────────────────────────────

HELP_TEXT = f"""\
{_C.BOLD}{APP_NAME}{_C.NC} — Self-hosted AI-powered personal knowledge base

{_C.CYAN}USAGE:{_C.NC}
    4dpocket <command> [options]

{_C.CYAN}GETTING STARTED:{_C.NC}
    4dpocket setup                         Interactive setup wizard
    4dpocket start                         Start server (runs setup if first time)
    4dpocket start --sqlite                Zero-config start (SQLite, no Docker)
    4dpocket start --postgres              PostgreSQL + Meilisearch (auto-starts Docker)
    4dpocket start --full                  Full stack (+ ChromaDB + Ollama)

{_C.CYAN}APP LIFECYCLE:{_C.NC}
    {_C.BOLD}start{_C.NC}  [opts]                        Start the server
    {_C.BOLD}stop{_C.NC}                                 Stop the server
    {_C.BOLD}restart{_C.NC} [opts]                       Restart the server
    {_C.BOLD}status{_C.NC}                               Show all service status
    {_C.BOLD}logs{_C.NC}   [server]                      Tail service logs

{_C.CYAN}START OPTIONS:{_C.NC}
    --sqlite               SQLite + FTS5 (zero-config)
    --postgres             PostgreSQL + Meilisearch (starts Docker services)
    --full                 All services (PostgreSQL + Meili + Chroma + Ollama)
    --host HOST            Override bind host (default: 0.0.0.0)
    --port PORT            Override bind port (default: 4040)
    --background, -d       Run in background (daemon mode)
    --reload               Enable auto-reload for development

{_C.CYAN}DATABASE:{_C.NC}
    {_C.BOLD}db init{_C.NC}                              Create tables (safe to re-run)
    {_C.BOLD}db reset{_C.NC}                             Drop + recreate database (DESTRUCTIVE)
    {_C.BOLD}db migrate{_C.NC}                           Run Alembic migrations
    {_C.BOLD}db shell{_C.NC}                             Open psql or sqlite3 CLI
    {_C.BOLD}db backup{_C.NC}   [--out PATH]             Snapshot DB + uploads + secret key (SQLite only)
    {_C.BOLD}db restore{_C.NC}  --from PATH [--force]   Restore from backup (DESTRUCTIVE, requires --force)

{_C.CYAN}EMBEDDINGS:{_C.NC}
    {_C.BOLD}embed reindex{_C.NC} [--user EMAIL] [--dry-run]  Re-embed all items (or one user's)

{_C.CYAN}AUTH:{_C.NC}
    {_C.BOLD}auth rotate-key{_C.NC} [--grace-days N]    Generate new secret key (moves old to .previous)

{_C.CYAN}DOCKER SERVICES:{_C.NC}
    {_C.BOLD}services up{_C.NC}   [postgres meili chroma ollama all]
    {_C.BOLD}services down{_C.NC}  [names...]
    {_C.BOLD}services status{_C.NC}

{_C.CYAN}MAINTENANCE:{_C.NC}
    {_C.BOLD}clean{_C.NC}                                Remove logs, PID files, caches
    {_C.BOLD}setup{_C.NC}                                Run interactive setup wizard
    {_C.BOLD}version{_C.NC}                              Show version

{_C.CYAN}EXAMPLES:{_C.NC}
    4dpocket setup                          # First-time config wizard
    4dpocket start                          # Start (auto-setup on first run)
    4dpocket start --sqlite                 # Quick start, no Docker
    4dpocket start --postgres -d            # Background with PostgreSQL
    4dpocket start --full                   # Full stack with all services
    4dpocket stop                           # Stop server
    4dpocket status                         # Check what's running
    4dpocket db reset                       # Reset database
    4dpocket services up postgres meili     # Start specific Docker services
    4dpocket logs                           # Tail server logs
"""


# ─── Main ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="4dpocket",
        description=f"{APP_NAME} - Self-hosted AI-powered personal knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    parser.add_argument("-V", "--version", action="version", version=f"4dpocket {_get_version()}")
    parser.add_argument("-h", "--help", action="store_true")

    sub = parser.add_subparsers(dest="command")

    # start
    p_start = sub.add_parser("start", help="Start the server")
    p_start.add_argument("--host", help="Bind host")
    p_start.add_argument("--port", type=int, help="Bind port")
    p_start.add_argument("--reload", action="store_true", help="Auto-reload (dev)")
    p_start.add_argument("--background", "-d", action="store_true", help="Run in background")
    p_start.add_argument("--sqlite", action="store_true", help="Use SQLite (zero-config)")
    p_start.add_argument("--postgres", action="store_true", help="Use PostgreSQL + Meilisearch")
    p_start.add_argument("--full", action="store_true", help="Full stack with all services")

    # stop
    sub.add_parser("stop", help="Stop the server")

    # restart
    p_restart = sub.add_parser("restart", help="Restart the server")
    p_restart.add_argument("--host", help="Bind host")
    p_restart.add_argument("--port", type=int, help="Bind port")
    p_restart.add_argument("--background", "-d", action="store_true", help="Run in background")
    p_restart.add_argument("--reload", action="store_true")
    p_restart.add_argument("--sqlite", action="store_true")
    p_restart.add_argument("--postgres", action="store_true")
    p_restart.add_argument("--full", action="store_true")

    # status
    sub.add_parser("status", help="Show service status")

    # logs
    p_logs = sub.add_parser("logs", help="Tail service logs")
    p_logs.add_argument("service", nargs="?", default="server", help="Service name (default: server)")

    # setup
    sub.add_parser("setup", help="Interactive setup wizard")

    # db
    p_db = sub.add_parser("db", help="Database management")
    p_db.add_argument("db_command",
                      choices=["init", "reset", "migrate", "shell", "backup", "restore"],
                      help="Database operation")
    p_db.add_argument("-y", "--yes", action="store_true",
                      help="Skip confirmation prompts")
    p_db.add_argument("--out", default=None,
                      help="[backup] Output archive path (default: ./data/backups/4dpocket-<ts>.tar.gz)")
    p_db.add_argument("--from", dest="from_path", default=None,
                      help="[restore] Archive to restore from (required)")
    p_db.add_argument("--force", action="store_true",
                      help="[restore] Required flag to confirm destructive restore")

    # embed
    p_embed = sub.add_parser("embed", help="Embedding management")
    p_embed.add_argument("embed_command", choices=["reindex"],
                         help="Embedding operation")
    p_embed.add_argument("--user", default=None,
                         help="[reindex] Scope to this user's email only")
    p_embed.add_argument("--dry-run", action="store_true",
                         help="[reindex] Print plan without making changes")

    # auth
    p_auth = sub.add_parser("auth", help="Auth management")
    p_auth.add_argument("auth_command", choices=["rotate-key"],
                        help="Auth operation")
    p_auth.add_argument("--grace-days", type=int, default=7,
                        help="[rotate-key] Days to mention in grace-period reminder (default: 7)")

    # services
    p_svc = sub.add_parser("services", help="Docker service management")
    p_svc.add_argument("action", choices=["up", "down", "status"], help="Action")
    p_svc.add_argument("targets", nargs="*", help="Service names")

    # clean
    sub.add_parser("clean", help="Remove logs, PID files, caches")

    # version
    sub.add_parser("version", help="Show version")

    # help
    sub.add_parser("help", help="Show full help")

    args = parser.parse_args()

    if args.help or args.command == "help":
        print(HELP_TEXT)
        return

    if args.command == "version":
        print(f"4dpocket {_get_version()}")
    elif args.command == "setup":
        cmd_setup(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "stop":
        cmd_stop(args)
    elif args.command == "restart":
        cmd_restart(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "logs":
        cmd_logs(args)
    elif args.command == "db":
        cmd_db(args)
    elif args.command == "embed":
        cmd_embed(args)
    elif args.command == "auth":
        cmd_auth(args)
    elif args.command == "services":
        cmd_services(args)
    elif args.command == "clean":
        cmd_clean(args)
    else:
        # Default: no command = start
        args.host = None
        args.port = None
        args.reload = False
        args.background = False
        args.sqlite = False
        args.postgres = False
        args.full = False
        args.profile = None
        cmd_start(args)


if __name__ == "__main__":
    main()
