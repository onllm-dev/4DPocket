"""4DPocket CLI — entry point for pip-installed and direct usage."""

import argparse
import os
from pathlib import Path

DEFAULT_DATA_DIR = Path.home() / ".4dpocket"


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


def _load_env_file(env_path):
    """Load .env file into os.environ without overriding existing vars."""
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key not in os.environ:
                os.environ[key] = value


def _prompt_choice(label, options, default="1"):
    """Display numbered options and return the user's choice."""
    print(f"  {label}")
    for num, desc in options:
        print(f"    {num}) {desc}")
    choice = input(f"\n  Choose [{default}]: ").strip() or default
    print()
    return choice


def setup_wizard():
    """Interactive first-run configuration wizard."""
    print()
    print("  4DPocket — Setup")
    print("  " + "-" * 40)
    print()

    config = {}
    data_dir = DEFAULT_DATA_DIR / "data"

    # ── Database ─────────────────────────────────────────────
    choice = _prompt_choice("Database:", [
        ("1", "SQLite        (zero-config, recommended for personal use)"),
        ("2", "PostgreSQL    (for larger deployments)"),
    ])

    if choice == "2":
        default_pg = "postgresql://4dp:4dp@localhost:5432/4dpocket"
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

    # ── AI Provider ──────────────────────────────────────────
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

    # ── Auth ─────────────────────────────────────────────────
    choice = _prompt_choice("Authentication:", [
        ("1", "Single user   (no login required)"),
        ("2", "Multi-user    (email/password registration)"),
    ])
    config["FDP_AUTH__MODE"] = "multi" if choice == "2" else "single"

    # ── Server ───────────────────────────────────────────────
    port = input("  Server port [4040]: ").strip() or "4040"
    config["FDP_SERVER__PORT"] = port
    print()

    # ── Defaults ─────────────────────────────────────────────
    config["FDP_STORAGE__BASE_PATH"] = str(data_dir)
    config["FDP_AI__AUTO_TAG"] = "true"
    config["FDP_AI__AUTO_SUMMARIZE"] = "true"
    config["FDP_AI__SYNC_ENRICHMENT"] = "true"
    config["FDP_SERVER__HOST"] = "0.0.0.0"
    config["FDP_SERVER__CORS_ORIGINS"] = f'["http://localhost:{port}"]'
    config["FDP_AI__EMBEDDING_PROVIDER"] = "local"
    config["FDP_AI__EMBEDDING_MODEL"] = "all-MiniLM-L6-v2"

    # ── Write config ─────────────────────────────────────────
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

    print(f"  Configuration saved to {env_path}")
    print(f"  Data directory: {data_dir}")
    print()
    print("  Run '4dpocket start' to launch the server.")
    print()

    return env_path


def cmd_start(args):
    """Start the 4DPocket server."""
    if _find_env_file() is None:
        print("\n  No configuration found. Running setup wizard...\n")
        env_path = setup_wizard()
    else:
        env_path = _find_env_file()

    if env_path:
        _load_env_file(env_path)

    host = args.host or os.environ.get("FDP_SERVER__HOST", "0.0.0.0")
    port = args.port or int(os.environ.get("FDP_SERVER__PORT", "4040"))

    print(f"  Starting 4DPocket on http://localhost:{port}")
    print()

    import uvicorn

    uvicorn.run(
        "fourdpocket.main:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level="info",
    )


def cmd_setup(_args):
    """Run the setup wizard."""
    setup_wizard()


def main():
    parser = argparse.ArgumentParser(
        prog="4dpocket",
        description="4DPocket - Self-hosted AI-powered personal knowledge base",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"4dpocket {_get_version()}",
    )

    sub = parser.add_subparsers(dest="command")

    p_start = sub.add_parser("start", help="Start the server")
    p_start.add_argument("--host", help="Bind host (default: from config)")
    p_start.add_argument("--port", type=int, help="Bind port (default: from config)")
    p_start.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    sub.add_parser("setup", help="Run interactive setup wizard")

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    else:
        # Default to start — ensure attributes exist
        if not hasattr(args, "host"):
            args.host = None
        if not hasattr(args, "port"):
            args.port = None
        if not hasattr(args, "reload"):
            args.reload = False
        cmd_start(args)


if __name__ == "__main__":
    main()
