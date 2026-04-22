#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════════
# 4DPocket — Application Management Script
#
# Single entry point for all development and deployment operations.
# Run ./app.sh help for full documentation.
# ═══════════════════════════════════════════════════════════════════

# ─── Colors & Helpers ────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()    { echo -e "${CYAN}==> $1${NC}"; }
success() { echo -e "${GREEN}==> $1${NC}"; }
warn()    { echo -e "${YELLOW}==> $1${NC}"; }
error()   { echo -e "${RED}==> ERROR: $1${NC}" >&2; }
step()    { echo -e "  ${GREEN}✓${NC} $1"; }
fail()    { echo -e "  ${RED}✗${NC} $1"; }

# ─── Constants ───────────────────────────────────────────────────

APP_NAME="4DPocket"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION=$(grep '^version' "$SCRIPT_DIR/pyproject.toml" | head -1 | sed 's/.*"\(.*\)"/\1/')

FRONTEND_PORT=5173

PID_DIR="$SCRIPT_DIR/.pids"
LOG_DIR="$SCRIPT_DIR/logs"

BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"
WORKER_PID_FILE="$PID_DIR/worker.pid"

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
WORKER_LOG="$LOG_DIR/worker.log"

# Docker container names
POSTGRES_CONTAINER="4dp-postgres"
MEILI_CONTAINER="4dp-meili"
CHROMA_CONTAINER="4dp-chromadb"
OLLAMA_CONTAINER="4dp-ollama"

# Default PostgreSQL credentials (overridable via env)
PG_USER="${PG_USER:-4dp}"
PG_PASSWORD="${PG_PASSWORD:-4dp}"
PG_DB="${PG_DB:-4dpocket}"
PG_PORT="${PG_PORT:-5432}"

# ─── Environment ─────────────────────────────────────────────────

detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if [ -f /etc/os-release ]; then
            # shellcheck disable=SC1091
            . /etc/os-release
            DISTRO="$ID"
        else
            DISTRO="unknown"
        fi
    else
        OS="unknown"
    fi
}

get_local_ip() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost"
    else
        hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost"
    fi
}

load_env() {
    if [ -f "$SCRIPT_DIR/.env" ]; then
        set -a
        # shellcheck disable=SC1091
        source "$SCRIPT_DIR/.env"
        set +a
    fi
}

check_command() {
    command -v "$1" &>/dev/null
}

get_backend_port() {
    echo "${FDP_SERVER__PORT:-4040}"
}

# ─── Prerequisite Checking ───────────────────────────────────────

check_prerequisites() {
    local missing=0

    # Python 3.12+
    if check_command python3; then
        local py_version
        py_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 12) else 1)' 2>/dev/null; then
            step "Python $py_version"
        else
            fail "Python $py_version (need 3.12+)"
            missing=1
        fi
    else
        fail "Python not found"
        missing=1
    fi

    # uv
    if check_command uv; then
        step "uv $(uv --version 2>/dev/null | awk '{print $2}')"
    else
        fail "uv not found"
        echo -e "    Install: ${YELLOW}curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
        missing=1
    fi

    # Node.js
    if check_command node; then
        step "Node.js $(node --version)"
    else
        fail "Node.js not found"
        missing=1
    fi

    # pnpm
    if check_command pnpm; then
        step "pnpm $(pnpm --version)"
    else
        fail "pnpm not found"
        echo -e "    Install: ${YELLOW}npm install -g pnpm${NC}"
        missing=1
    fi

    # Git
    if check_command git; then
        step "git $(git --version | awk '{print $3}')"
    else
        fail "git not found"
        missing=1
    fi

    # Optional tools
    if check_command docker; then
        step "Docker $(docker --version 2>/dev/null | awk '{print $3}' | tr -d ',')"
    else
        echo -e "  ${DIM}-${NC} Docker ${DIM}(optional — for PostgreSQL, Meilisearch, Ollama)${NC}"
    fi

    if check_command tesseract; then
        step "Tesseract OCR"
    else
        echo -e "  ${DIM}-${NC} Tesseract OCR ${DIM}(optional — for image text extraction)${NC}"
    fi

    return $missing
}

install_deps_for_os() {
    detect_os
    info "Installing system dependencies for $OS..."

    case "$OS" in
        macos)
            if ! check_command brew; then
                error "Homebrew not found. Install from https://brew.sh"
                return 1
            fi
            check_command python3 || brew install python@3.12
            check_command uv      || { curl -LsSf https://astral.sh/uv/install.sh | sh; }
            check_command node    || brew install node
            check_command pnpm    || npm install -g pnpm
            ;;
        linux)
            case "${DISTRO:-unknown}" in
                ubuntu|debian)
                    sudo apt-get update -qq
                    sudo apt-get install -y python3 python3-dev python3-venv curl git
                    check_command uv   || { curl -LsSf https://astral.sh/uv/install.sh | sh; }
                    check_command node || { curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs; }
                    check_command pnpm || npm install -g pnpm
                    ;;
                fedora|rhel|centos)
                    sudo dnf install -y python3 python3-devel curl git nodejs
                    check_command uv   || { curl -LsSf https://astral.sh/uv/install.sh | sh; }
                    check_command pnpm || npm install -g pnpm
                    ;;
                arch|manjaro)
                    sudo pacman -S --needed python curl git nodejs npm
                    check_command uv   || { curl -LsSf https://astral.sh/uv/install.sh | sh; }
                    check_command pnpm || npm install -g pnpm
                    ;;
                *)
                    error "Unsupported Linux distribution: ${DISTRO:-unknown}"
                    echo "Install manually: Python 3.12+, uv, Node.js 22+, pnpm, git"
                    return 1
                    ;;
            esac
            ;;
        *)
            error "Unsupported OS: $OSTYPE"
            return 1
            ;;
    esac

    success "System dependencies installed."
}

# ─── Process Management ─────────────────────────────────────────

is_running() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$pid_file"
    fi
    return 1
}

kill_by_pid_file() {
    local pid_file="$1"
    local name="$2"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            # Wait up to 5s for graceful shutdown
            local i=0
            while kill -0 "$pid" 2>/dev/null && [ $i -lt 50 ]; do
                sleep 0.1
                i=$((i + 1))
            done
            # Force kill if still alive
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            step "$name stopped (was PID: $pid)"
        fi
        rm -f "$pid_file"
    fi
}

kill_port() {
    local port="$1"
    local pids
    pids=$(lsof -ti:"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill 2>/dev/null || true
        sleep 1
    fi
}

# ─── Start Functions ─────────────────────────────────────────────

start_backend() {
    local mode="${1:-dev}"
    local port
    port=$(get_backend_port)

    if is_running "$BACKEND_PID_FILE"; then
        warn "Backend already running (PID: $(cat "$BACKEND_PID_FILE"))"
        return 0
    fi

    mkdir -p "$PID_DIR" "$LOG_DIR"
    kill_port "$port"

    # Ensure backend deps
    if [ ! -d "$SCRIPT_DIR/.venv" ]; then
        info "Installing backend dependencies..."
        cd "$SCRIPT_DIR"
        uv sync --all-extras --quiet
        step "Backend dependencies installed"
    fi

    info "Starting backend (port $port, mode: $mode)..."
    cd "$SCRIPT_DIR"

    if [ "$mode" = "dev" ]; then
        uv run uvicorn fourdpocket.main:app \
            --host 0.0.0.0 --port "$port" --reload \
            > "$BACKEND_LOG" 2>&1 &
    else
        uv run uvicorn fourdpocket.main:app \
            --host 0.0.0.0 --port "$port" \
            > "$BACKEND_LOG" 2>&1 &
    fi

    local pid=$!
    sleep 2

    if kill -0 "$pid" 2>/dev/null; then
        echo "$pid" > "$BACKEND_PID_FILE"
        step "Backend started (PID: $pid, port: $port)"
    else
        fail "Backend failed to start (port in use or missing command)"
        echo -e "    ${DIM}Check: tail -f $BACKEND_LOG${NC}"
        return 1
    fi
}

start_frontend() {
    local mode="${1:-dev}"

    if [ "$mode" = "prod" ]; then
        # Production: backend serves from frontend/dist
        if [ ! -d "$SCRIPT_DIR/frontend/dist" ]; then
            warn "frontend/dist not found. Building..."
            do_build
        fi
        step "Frontend served by backend from frontend/dist/"
        return 0
    fi

    if is_running "$FRONTEND_PID_FILE"; then
        warn "Frontend already running (PID: $(cat "$FRONTEND_PID_FILE"))"
        return 0
    fi

    mkdir -p "$PID_DIR" "$LOG_DIR"
    kill_port "$FRONTEND_PORT"

    # Ensure frontend deps
    if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
        info "Installing frontend dependencies..."
        cd "$SCRIPT_DIR/frontend"
        pnpm install --silent
        step "Frontend dependencies installed"
    fi

    info "Starting frontend dev server (port $FRONTEND_PORT)..."
    cd "$SCRIPT_DIR/frontend"
    pnpm dev --host 0.0.0.0 > "$FRONTEND_LOG" 2>&1 &

    local pid=$!
    echo "$pid" > "$FRONTEND_PID_FILE"
    cd "$SCRIPT_DIR"
    sleep 3

    if kill -0 "$pid" 2>/dev/null; then
        step "Frontend started (PID: $pid, port: $FRONTEND_PORT)"
    else
        fail "Frontend failed to start"
        echo -e "    ${DIM}Check: tail -f $FRONTEND_LOG${NC}"
        return 1
    fi
}

kill_stale_workers() {
    # Kill Huey worker processes NOT tracked by our PID file.
    # Prevents zombies (started outside app.sh or from prior crashes) from
    # stealing tasks and poisoning the SQLite task queue with stale registries.
    local tracked_pid=""
    if [ -f "$WORKER_PID_FILE" ]; then
        tracked_pid=$(cat "$WORKER_PID_FILE" 2>/dev/null || echo "")
    fi
    local stale
    stale=$(pgrep -f "fourdpocket.workers.huey_worker" 2>/dev/null | grep -v "^${tracked_pid:-__none__}$" || true)
    if [ -n "$stale" ]; then
        warn "Found stale Huey worker process(es): $(echo "$stale" | tr '\n' ' ')"
        echo "$stale" | xargs kill 2>/dev/null || true
        sleep 1
        local survivors
        survivors=$(pgrep -f "fourdpocket.workers.huey_worker" 2>/dev/null | grep -v "^${tracked_pid:-__none__}$" || true)
        [ -n "$survivors" ] && echo "$survivors" | xargs kill -9 2>/dev/null || true
        step "Cleaned up stale workers"
    fi
}

start_worker() {
    if is_running "$WORKER_PID_FILE"; then
        warn "Worker already running (PID: $(cat "$WORKER_PID_FILE"))"
        kill_stale_workers
        return 0
    fi

    kill_stale_workers

    mkdir -p "$PID_DIR" "$LOG_DIR"

    info "Starting Huey background worker..."
    cd "$SCRIPT_DIR"

    uv run python -m fourdpocket.workers.huey_worker \
        --workers "${HUEY_WORKERS:-2}" --worker-type thread \
        > "$WORKER_LOG" 2>&1 &

    local pid=$!
    sleep 2

    if kill -0 "$pid" 2>/dev/null; then
        echo "$pid" > "$WORKER_PID_FILE"
        step "Worker started (PID: $pid, ${HUEY_WORKERS:-2} threads)"
    else
        fail "Worker failed to start (port in use or missing command)"
        echo -e "    ${DIM}Check: tail -f $WORKER_LOG${NC}"
        return 1
    fi
}

# ─── Stop Functions ──────────────────────────────────────────────

stop_backend()  { kill_by_pid_file "$BACKEND_PID_FILE" "Backend"; }
stop_frontend() { kill_by_pid_file "$FRONTEND_PID_FILE" "Frontend"; }
stop_worker()   { kill_by_pid_file "$WORKER_PID_FILE" "Worker"; }

stop_all() {
    info "Stopping all services..."
    stop_worker
    stop_frontend
    stop_backend
    success "All services stopped."
}

# ─── Docker Service Management ──────────────────────────────────

docker_ensure() {
    if ! check_command docker; then
        error "Docker is required but not installed."
        echo -e "  Install: ${YELLOW}https://docs.docker.com/get-docker/${NC}"
        return 1
    fi
    if ! docker info &>/dev/null 2>&1; then
        error "Docker daemon is not running."
        return 1
    fi
}

service_is_running() {
    docker ps --filter "name=^${1}$" --format '{{.Names}}' 2>/dev/null | grep -q "^${1}$"
}

service_exists() {
    docker ps -a --filter "name=^${1}$" --format '{{.Names}}' 2>/dev/null | grep -q "^${1}$"
}

start_postgres() {
    docker_ensure || return 1

    if service_is_running "$POSTGRES_CONTAINER"; then
        step "PostgreSQL already running"
        return 0
    fi

    info "Starting PostgreSQL..."

    if service_exists "$POSTGRES_CONTAINER"; then
        docker start "$POSTGRES_CONTAINER" >/dev/null
    else
        docker run -d --name "$POSTGRES_CONTAINER" \
            -p "${PG_PORT}:5432" \
            -e POSTGRES_USER="$PG_USER" \
            -e POSTGRES_PASSWORD="$PG_PASSWORD" \
            -e POSTGRES_DB="$PG_DB" \
            -v 4dp-postgres:/var/lib/postgresql/data \
            postgres:16-alpine >/dev/null
    fi

    # Wait for ready (up to 30s)
    local i=0
    while ! docker exec "$POSTGRES_CONTAINER" pg_isready -U "$PG_USER" -d "$PG_DB" &>/dev/null && [ $i -lt 30 ]; do
        sleep 1
        i=$((i + 1))
    done

    if docker exec "$POSTGRES_CONTAINER" pg_isready -U "$PG_USER" -d "$PG_DB" &>/dev/null; then
        step "PostgreSQL ready (port: $PG_PORT, db: $PG_DB)"
    else
        fail "PostgreSQL failed to start within 30s"
        return 1
    fi
}

start_meilisearch() {
    docker_ensure || return 1
    local meili_key="${FDP_SEARCH__MEILI_MASTER_KEY:-devkey123}"

    if service_is_running "$MEILI_CONTAINER"; then
        step "Meilisearch already running"
        return 0
    fi

    info "Starting Meilisearch..."

    if service_exists "$MEILI_CONTAINER"; then
        docker start "$MEILI_CONTAINER" >/dev/null
    else
        docker run -d --name "$MEILI_CONTAINER" \
            -p 7700:7700 \
            -e MEILI_MASTER_KEY="$meili_key" \
            -v 4dp-meili:/meili_data \
            getmeili/meilisearch:v1.12 >/dev/null
    fi

    # Wait for healthy (up to 30s)
    local i=0
    while ! curl -sf http://localhost:7700/health &>/dev/null && [ $i -lt 30 ]; do
        sleep 1
        i=$((i + 1))
    done

    if curl -sf http://localhost:7700/health &>/dev/null; then
        step "Meilisearch ready (port: 7700)"
    else
        fail "Meilisearch failed to start within 30s"
        return 1
    fi
}

start_chromadb() {
    docker_ensure || return 1

    if service_is_running "$CHROMA_CONTAINER"; then
        step "ChromaDB already running"
        return 0
    fi

    info "Starting ChromaDB..."

    if service_exists "$CHROMA_CONTAINER"; then
        docker start "$CHROMA_CONTAINER" >/dev/null
    else
        docker run -d --name "$CHROMA_CONTAINER" \
            -p 8000:8000 \
            -v 4dp-chroma:/chroma/chroma \
            chromadb/chroma:latest >/dev/null
    fi

    sleep 3
    if service_is_running "$CHROMA_CONTAINER"; then
        step "ChromaDB ready (port: 8000)"
    else
        fail "ChromaDB failed to start"
        return 1
    fi
}

start_ollama() {
    docker_ensure || return 1

    # Prefer native Ollama if available
    if check_command ollama; then
        if curl -sf http://localhost:11434/api/tags &>/dev/null; then
            step "Ollama running natively (skipping Docker)"
            return 0
        fi
    fi

    if service_is_running "$OLLAMA_CONTAINER"; then
        step "Ollama already running"
        return 0
    fi

    info "Starting Ollama..."

    if service_exists "$OLLAMA_CONTAINER"; then
        docker start "$OLLAMA_CONTAINER" >/dev/null
    else
        docker run -d --name "$OLLAMA_CONTAINER" \
            -p 11434:11434 \
            -v 4dp-ollama:/root/.ollama \
            ollama/ollama:latest >/dev/null
    fi

    sleep 3
    if service_is_running "$OLLAMA_CONTAINER"; then
        step "Ollama ready (port: 11434)"
    else
        fail "Ollama failed to start"
        return 1
    fi
}

stop_docker_service() {
    local name="$1"
    if service_is_running "$name"; then
        docker stop "$name" >/dev/null 2>&1
        step "$name stopped"
    else
        echo -e "  ${DIM}○${NC} $name (not running)"
    fi
}

remove_docker_service() {
    local name="$1"
    if service_exists "$name"; then
        docker rm -f "$name" >/dev/null 2>&1
        step "$name removed"
    fi
}

services_up() {
    local services=("$@")

    if [ ${#services[@]} -eq 0 ]; then
        # Auto-detect from .env
        load_env
        local db_url="${FDP_DATABASE__URL:-sqlite:///./data/4dpocket.db}"
        local search="${FDP_SEARCH__BACKEND:-sqlite}"
        local ai="${FDP_AI__CHAT_PROVIDER:-ollama}"

        if [[ "$db_url" == postgresql* ]]; then
            start_postgres || true
        fi
        if [ "$search" = "meilisearch" ]; then
            start_meilisearch || true
        fi
        if [ "$ai" = "ollama" ]; then
            start_ollama || true
        fi
        return
    fi

    for svc in "${services[@]}"; do
        case "$svc" in
            postgres|pg|postgresql)  start_postgres ;;
            meilisearch|meili)       start_meilisearch ;;
            chromadb|chroma)         start_chromadb ;;
            ollama)                  start_ollama ;;
            all)
                start_postgres
                start_meilisearch
                start_chromadb
                start_ollama
                ;;
            *)  warn "Unknown service: $svc (use: postgres, meilisearch, chromadb, ollama, all)" ;;
        esac
    done
}

services_down() {
    local services=("$@")

    if [ ${#services[@]} -eq 0 ]; then
        services=(all)
    fi

    for svc in "${services[@]}"; do
        case "$svc" in
            postgres|pg|postgresql)  stop_docker_service "$POSTGRES_CONTAINER" ;;
            meilisearch|meili)       stop_docker_service "$MEILI_CONTAINER" ;;
            chromadb|chroma)         stop_docker_service "$CHROMA_CONTAINER" ;;
            ollama)                  stop_docker_service "$OLLAMA_CONTAINER" ;;
            all)
                stop_docker_service "$POSTGRES_CONTAINER"
                stop_docker_service "$MEILI_CONTAINER"
                stop_docker_service "$CHROMA_CONTAINER"
                stop_docker_service "$OLLAMA_CONTAINER"
                ;;
        esac
    done
}

services_status() {
    echo -e "${BOLD}Docker Services:${NC}"
    local containers=("$POSTGRES_CONTAINER" "$MEILI_CONTAINER" "$CHROMA_CONTAINER" "$OLLAMA_CONTAINER")
    local labels=("PostgreSQL" "Meilisearch" "ChromaDB" "Ollama")

    for i in "${!containers[@]}"; do
        local name="${containers[$i]}"
        local label="${labels[$i]}"
        if service_is_running "$name"; then
            local port_info
            port_info=$(docker port "$name" 2>/dev/null | head -1 | sed 's/.*://' || echo "?")
            echo -e "  ${GREEN}●${NC} $label ${DIM}($name, port: $port_info)${NC}"
        elif service_exists "$name"; then
            echo -e "  ${YELLOW}●${NC} $label ${DIM}($name, stopped)${NC}"
        else
            echo -e "  ${DIM}○${NC} $label ${DIM}(not created)${NC}"
        fi
    done
}

# ─── Setup ───────────────────────────────────────────────────────

do_setup() {
    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║     $APP_NAME v$VERSION — Setup              ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
    echo ""

    local install_system=false

    # Parse setup flags
    for arg in "$@"; do
        case "$arg" in
            --deps|--install|-d) install_system=true ;;
        esac
    done

    detect_os
    info "Detected: $OS"

    # Optionally install system deps
    if $install_system; then
        install_deps_for_os
        echo ""
    fi

    # Check prerequisites
    info "Checking prerequisites..."
    if ! check_prerequisites; then
        echo ""
        error "Missing required tools. Run: ./app.sh setup --deps"
        return 1
    fi
    echo ""

    # Create directories
    mkdir -p "$PID_DIR" "$LOG_DIR" "$SCRIPT_DIR/data"
    step "Directories ready (logs/, data/)"

    # Backend dependencies
    info "Installing backend dependencies..."
    cd "$SCRIPT_DIR"
    uv sync --all-extras --quiet
    step "Backend dependencies installed"

    # Frontend dependencies
    info "Installing frontend dependencies..."
    cd "$SCRIPT_DIR/frontend"
    pnpm install --silent
    step "Frontend dependencies installed"

    # Build frontend for production serving
    info "Building frontend..."
    cd "$SCRIPT_DIR/frontend"
    pnpm build 2>&1 | tail -5
    step "Frontend built (frontend/dist/)"
    cd "$SCRIPT_DIR"

    # Chrome extension (optional, but part of a full setup)
    if [ -d "$SCRIPT_DIR/extension" ]; then
        info "Installing extension dependencies..."
        cd "$SCRIPT_DIR/extension"
        pnpm install --silent
        step "Extension dependencies installed"

        info "Building Chrome extension..."
        pnpm build 2>&1 | tail -5
        step "Extension built (extension/dist/chrome-mv3/)"
        cd "$SCRIPT_DIR"
    fi

    # Create .env if missing
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        step "Created .env from .env.example"
        echo ""
        warn "Edit .env to configure your database, AI provider, etc."
    else
        step ".env already exists"
    fi

    echo ""
    success "Setup complete!"
    echo ""
    echo -e "  Quick start:  ${YELLOW}./app.sh start --sqlite${NC}        ${DIM}(zero-config, no Docker)${NC}"
    echo -e "  With Postgres: ${YELLOW}./app.sh start --postgres${NC}      ${DIM}(auto-starts Docker services)${NC}"
    echo -e "  Full stack:    ${YELLOW}./app.sh start --full${NC}          ${DIM}(PostgreSQL + Meili + Chroma + Ollama)${NC}"
    echo -e "  From .env:     ${YELLOW}./app.sh start${NC}                ${DIM}(uses your .env configuration)${NC}"
}

# ─── Start All ───────────────────────────────────────────────────

do_start() {
    local mode="dev"
    local start_backend=true
    local start_frontend=true
    local start_worker=true
    local profile=""
    local custom_port=""

    # Parse options
    while [ $# -gt 0 ]; do
        case "$1" in
            --backend|-b)    start_frontend=false; start_worker=false ;;
            --frontend|-f)   start_backend=false; start_worker=false ;;
            --worker|-w)     start_backend=false; start_frontend=false ;;
            --no-worker)     start_worker=false ;;
            --no-frontend)   start_frontend=false ;;
            --dev)           mode="dev" ;;
            --prod)          mode="prod" ;;
            --sqlite)        profile="sqlite" ;;
            --postgres)      profile="postgres" ;;
            --full)          profile="full" ;;
            --port=*)        custom_port="${1#*=}" ;;
            *)               warn "Unknown option: $1" ;;
        esac
        shift
    done

    load_env

    # Apply custom port
    if [ -n "$custom_port" ]; then
        export FDP_SERVER__PORT="$custom_port"
    fi

    local port
    port=$(get_backend_port)

    echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║     $APP_NAME v$VERSION                       ║${NC}"
    echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
    echo ""

    # Apply profile (sets env vars and starts Docker services)
    case "$profile" in
        sqlite)
            export FDP_DATABASE__URL="sqlite:///./data/4dpocket.db"
            export FDP_SEARCH__BACKEND="sqlite"
            info "Profile: SQLite (zero-config)"
            ;;
        postgres)
            start_postgres || return 1
            start_meilisearch || return 1
            export FDP_DATABASE__URL="${FDP_DATABASE__URL:-postgresql://$PG_USER:$PG_PASSWORD@localhost:$PG_PORT/$PG_DB}"
            export FDP_SEARCH__BACKEND="${FDP_SEARCH__BACKEND:-meilisearch}"
            export FDP_SEARCH__MEILI_URL="${FDP_SEARCH__MEILI_URL:-http://localhost:7700}"
            export FDP_SEARCH__MEILI_MASTER_KEY="${FDP_SEARCH__MEILI_MASTER_KEY:-devkey123}"
            info "Profile: PostgreSQL + Meilisearch"
            ;;
        full)
            start_postgres || return 1
            start_meilisearch || return 1
            start_chromadb || return 1
            start_ollama || return 1
            export FDP_DATABASE__URL="${FDP_DATABASE__URL:-postgresql://$PG_USER:$PG_PASSWORD@localhost:$PG_PORT/$PG_DB}"
            export FDP_SEARCH__BACKEND="${FDP_SEARCH__BACKEND:-meilisearch}"
            export FDP_SEARCH__MEILI_URL="${FDP_SEARCH__MEILI_URL:-http://localhost:7700}"
            export FDP_SEARCH__MEILI_MASTER_KEY="${FDP_SEARCH__MEILI_MASTER_KEY:-devkey123}"
            export FDP_AI__CHAT_PROVIDER="ollama"
            export FDP_AI__OLLAMA_URL="http://localhost:11434"
            info "Profile: Full stack (PostgreSQL + Meilisearch + ChromaDB + Ollama)"
            ;;
        "")
            # No profile — auto-start Docker services that .env requires
            local db_url="${FDP_DATABASE__URL:-sqlite:///./data/4dpocket.db}"
            if [[ "$db_url" == postgresql* ]] && check_command docker; then
                start_postgres || true
            fi
            if [ "${FDP_SEARCH__BACKEND:-sqlite}" = "meilisearch" ] && check_command docker; then
                start_meilisearch || true
            fi
            ;;
    esac

    echo ""

    # Start application services
    if $start_backend; then
        start_backend "$mode" || return 1
    fi
    if $start_frontend; then
        start_frontend "$mode" || return 1
    fi
    if $start_worker; then
        start_worker || return 1
    fi

    # Print access info
    local local_ip
    local_ip=$(get_local_ip)

    echo ""
    success "$APP_NAME is running!"
    echo ""

    if [ "$mode" = "dev" ] && $start_frontend; then
        echo -e "  ${BOLD}Frontend:${NC}  http://localhost:$FRONTEND_PORT"
        echo -e "  ${BOLD}Backend:${NC}   http://localhost:$port"
        echo -e "  ${BOLD}API Docs:${NC}  http://localhost:$port/docs"
        echo -e "  ${BOLD}Network:${NC}   http://$local_ip:$FRONTEND_PORT"
    else
        echo -e "  ${BOLD}App:${NC}       http://localhost:$port"
        echo -e "  ${BOLD}API Docs:${NC}  http://localhost:$port/docs"
        echo -e "  ${BOLD}Network:${NC}   http://$local_ip:$port"
    fi

    echo ""
    echo -e "  ${DIM}Logs:    ./app.sh logs [backend|frontend|worker|all]${NC}"
    echo -e "  ${DIM}Status:  ./app.sh status${NC}"
    echo -e "  ${DIM}Stop:    ./app.sh stop${NC}"
}

# ─── Status ──────────────────────────────────────────────────────

do_status() {
    load_env
    local port
    port=$(get_backend_port)

    echo -e "${BOLD}$APP_NAME v$VERSION${NC}"
    echo ""

    echo -e "${BOLD}Application:${NC}"

    if is_running "$BACKEND_PID_FILE"; then
        echo -e "  ${GREEN}●${NC} Backend    PID: $(cat "$BACKEND_PID_FILE")  Port: $port"
    else
        echo -e "  ${RED}●${NC} Backend    not running"
    fi

    if is_running "$FRONTEND_PID_FILE"; then
        echo -e "  ${GREEN}●${NC} Frontend   PID: $(cat "$FRONTEND_PID_FILE")  Port: $FRONTEND_PORT"
    else
        echo -e "  ${DIM}○${NC} Frontend   not running"
    fi

    if is_running "$WORKER_PID_FILE"; then
        echo -e "  ${GREEN}●${NC} Worker     PID: $(cat "$WORKER_PID_FILE")"
    else
        echo -e "  ${DIM}○${NC} Worker     not running"
    fi

    echo ""

    if check_command docker && docker info &>/dev/null 2>&1; then
        services_status
        echo ""
    fi

    echo -e "${BOLD}Configuration (.env):${NC}"
    local db_url="${FDP_DATABASE__URL:-sqlite:///./data/4dpocket.db}"
    if [[ "$db_url" == postgresql* ]]; then
        echo -e "  Database: PostgreSQL"
    else
        echo -e "  Database: SQLite"
    fi
    echo -e "  Search:   ${FDP_SEARCH__BACKEND:-sqlite}"
    echo -e "  AI:       ${FDP_AI__CHAT_PROVIDER:-ollama}"
    echo -e "  Auth:     ${FDP_AUTH__MODE:-single}"
}

# ─── Logs ────────────────────────────────────────────────────────

do_logs() {
    local service="${1:-backend}"

    case "$service" in
        backend|b)
            [ -f "$BACKEND_LOG" ] && tail -f "$BACKEND_LOG" || warn "No backend log at $BACKEND_LOG"
            ;;
        frontend|f)
            [ -f "$FRONTEND_LOG" ] && tail -f "$FRONTEND_LOG" || warn "No frontend log at $FRONTEND_LOG"
            ;;
        worker|w)
            [ -f "$WORKER_LOG" ] && tail -f "$WORKER_LOG" || warn "No worker log at $WORKER_LOG"
            ;;
        all|a)
            tail -f "$BACKEND_LOG" "$FRONTEND_LOG" "$WORKER_LOG" 2>/dev/null || warn "No logs found"
            ;;
        *)
            warn "Unknown log: $service (use: backend, frontend, worker, all)"
            ;;
    esac
}

# ─── Build ───────────────────────────────────────────────────────

do_build() {
    # Parse options — by default build both frontend + extension.
    local build_frontend=true
    local build_extension=true
    for arg in "$@"; do
        case "$arg" in
            --frontend|-f) build_extension=false ;;
            --extension|-e) build_frontend=false ;;
            --all|-a) build_frontend=true; build_extension=true ;;
        esac
    done

    if $build_frontend; then
        info "Building frontend..."
        cd "$SCRIPT_DIR/frontend"
        if [ ! -d "node_modules" ]; then
            info "Installing frontend dependencies first..."
            pnpm install --silent
        fi
        pnpm build
        cd "$SCRIPT_DIR"
        success "Frontend built (frontend/dist/)"
        echo -e "  ${DIM}Backend serves these files automatically at /.*${NC}"
    fi

    if $build_extension && [ -d "$SCRIPT_DIR/extension" ]; then
        info "Building Chrome extension..."
        cd "$SCRIPT_DIR/extension"
        if [ ! -d "node_modules" ]; then
            info "Installing extension dependencies first..."
            pnpm install --silent
        fi
        pnpm build
        cd "$SCRIPT_DIR"
        success "Chrome extension built (extension/dist/chrome-mv3/)"
        echo -e "  ${DIM}Load unpacked in chrome://extensions from that directory.${NC}"
    fi
}

# ─── Test & Lint ─────────────────────────────────────────────────

do_test() {
    info "Running tests..."
    cd "$SCRIPT_DIR"
    uv run pytest tests/ -q "$@"
}

do_lint() {
    info "Running linter..."
    cd "$SCRIPT_DIR"
    uv run ruff check src/ tests/
    success "Lint passed."
}

# ─── Database Management ────────────────────────────────────────

do_db() {
    local cmd="${1:-help}"
    shift 2>/dev/null || true

    load_env
    local db_url="${FDP_DATABASE__URL:-sqlite:///./data/4dpocket.db}"

    case "$cmd" in
        init)
            info "Initializing database..."
            cd "$SCRIPT_DIR"
            uv run python -c "from fourdpocket.db.session import init_db; init_db(); print('Done.')"
            success "Database tables created."
            ;;

        reset)
            warn "This will DESTROY ALL DATA in the database."
            echo -n "  Type 'yes' to confirm: "
            read -r confirm
            if [ "$confirm" != "yes" ]; then
                echo "  Cancelled."
                return 0
            fi

            if [[ "$db_url" == postgresql* ]]; then
                local pg_db_name
                pg_db_name=$(echo "$db_url" | sed 's|.*/||')
                local pg_base_url
                pg_base_url=$(echo "$db_url" | sed 's|/[^/]*$|/postgres|')

                info "Resetting PostgreSQL database: $pg_db_name..."

                # Terminate active connections
                psql "$pg_base_url" -c \
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$pg_db_name' AND pid <> pg_backend_pid();" \
                    >/dev/null 2>&1 || true

                psql "$pg_base_url" -c "DROP DATABASE IF EXISTS \"$pg_db_name\";" || {
                    error "Failed to drop database."
                    return 1
                }
                psql "$pg_base_url" -c "CREATE DATABASE \"$pg_db_name\" OWNER \"$PG_USER\";"

                cd "$SCRIPT_DIR"
                FDP_DATABASE__URL="$db_url" uv run python -c \
                    "from fourdpocket.db.session import init_db; init_db()"
                success "PostgreSQL database '$pg_db_name' reset and reinitialized."
            else
                local db_path
                db_path=$(echo "$db_url" | sed 's|sqlite:///||')
                info "Resetting SQLite database: $db_path..."
                rm -f "$db_path" "${db_path}-journal" "${db_path}-shm" "${db_path}-wal"

                cd "$SCRIPT_DIR"
                uv run python -c "from fourdpocket.db.session import init_db; init_db()"
                success "SQLite database reset and reinitialized."
            fi
            ;;

        migrate)
            info "Running Alembic migrations..."
            cd "$SCRIPT_DIR"
            uv run alembic upgrade head
            success "Migrations applied."
            ;;

        shell)
            if [[ "$db_url" == postgresql* ]]; then
                info "Opening PostgreSQL shell..."
                exec psql "$db_url"
            else
                local db_path
                db_path=$(echo "$db_url" | sed 's|sqlite:///||')
                if [ ! -f "$db_path" ]; then
                    warn "Database file not found: $db_path"
                    warn "Run './app.sh db init' first."
                    return 1
                fi
                info "Opening SQLite shell..."
                exec sqlite3 "$db_path"
            fi
            ;;

        *)
            echo "Usage: ./app.sh db <command>"
            echo ""
            echo "Commands:"
            echo "  init      Create all tables (safe to re-run)"
            echo "  reset     Drop and recreate database (DESTRUCTIVE)"
            echo "  migrate   Run Alembic migrations"
            echo "  shell     Open interactive database CLI (psql / sqlite3)"
            ;;
    esac
}

# ─── Docker Compose ──────────────────────────────────────────────

do_docker() {
    local cmd="${1:-help}"
    shift 2>/dev/null || true

    docker_ensure || return 1

    case "$cmd" in
        up)
            info "Starting Docker compose stack..."
            docker compose -f "$SCRIPT_DIR/docker-compose.yml" up -d "$@"
            success "Stack started."
            echo -e "  App: ${YELLOW}http://localhost:${FDP_PORT:-4040}${NC}"
            ;;
        down)
            info "Stopping Docker compose stack..."
            docker compose -f "$SCRIPT_DIR/docker-compose.yml" down "$@"
            success "Stack stopped."
            ;;
        build)
            info "Building Docker image..."
            docker compose -f "$SCRIPT_DIR/docker-compose.yml" build "$@"
            success "Image built."
            ;;
        logs)
            docker compose -f "$SCRIPT_DIR/docker-compose.yml" logs -f "$@"
            ;;
        simple)
            info "Starting minimal Docker stack (SQLite only)..."
            docker compose -f "$SCRIPT_DIR/docker-compose.simple.yml" up -d "$@"
            success "Minimal stack started."
            echo -e "  App: ${YELLOW}http://localhost:${FDP_PORT:-4040}${NC}"
            ;;
        *)
            echo "Usage: ./app.sh docker <command>"
            echo ""
            echo "Commands:"
            echo "  up       Start full stack (PostgreSQL + app + worker)"
            echo "  down     Stop full stack"
            echo "  build    Build Docker image"
            echo "  logs     Tail compose logs (pass service name to filter)"
            echo "  simple   Start minimal stack (SQLite, single container)"
            ;;
    esac
}

# ─── Clean ───────────────────────────────────────────────────────

do_clean() {
    info "Cleaning up..."

    # Stop running processes first
    stop_all 2>/dev/null || true

    rm -rf "$PID_DIR"
    rm -rf "$LOG_DIR"
    rm -rf "$SCRIPT_DIR/frontend/dist"
    rm -rf "$SCRIPT_DIR/frontend/.vite"
    rm -rf "$SCRIPT_DIR/extension/dist"
    rm -rf "$SCRIPT_DIR/extension/.output"
    rm -rf "$SCRIPT_DIR/extension/.wxt"
    rm -rf "$SCRIPT_DIR/.pytest_cache"
    rm -rf "$SCRIPT_DIR/.ruff_cache"
    rm -rf "$SCRIPT_DIR/.mypy_cache"
    rm -rf "$SCRIPT_DIR/htmlcov"
    rm -f "$SCRIPT_DIR/.coverage"
    find "$SCRIPT_DIR/src" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

    success "Clean complete."
}

# ─── Help ────────────────────────────────────────────────────────

show_help() {
    cat <<EOF
${BOLD}$APP_NAME v$VERSION${NC} — Self-hosted AI-powered personal knowledge base

${CYAN}USAGE:${NC}
    ./app.sh <command> [options]

${CYAN}GETTING STARTED:${NC}
    ./app.sh setup                         Install deps, build frontend, create .env
    ./app.sh setup --deps                  Also install system packages (Python, Node, etc.)
    ./app.sh start                         Start all services (reads .env config)
    ./app.sh start --sqlite                Zero-config start (SQLite, no Docker needed)
    ./app.sh start --postgres              PostgreSQL + Meilisearch (auto-starts Docker)
    ./app.sh start --full                  Full stack (+ ChromaDB + Ollama)

${CYAN}APP LIFECYCLE:${NC}
    ${BOLD}start${NC}  [opts]                        Start services
    ${BOLD}stop${NC}   [--backend|--frontend|--worker] Stop services
    ${BOLD}restart${NC} [opts]                        Restart services
    ${BOLD}status${NC}                                Show all service status
    ${BOLD}logs${NC}   [backend|frontend|worker|all]  Tail service logs

${CYAN}START OPTIONS:${NC}
    --backend, -b          Backend API server only
    --frontend, -f         Frontend dev server only
    --worker, -w           Huey background worker only
    --no-worker            Skip background worker
    --no-frontend          Skip frontend dev server
    --dev                  Development mode with hot reload (default)
    --prod                 Production mode (serve from frontend/dist)
    --sqlite               SQLite + FTS5 (zero-config)
    --postgres             PostgreSQL + Meilisearch (starts Docker services)
    --full                 All services (PostgreSQL + Meili + Chroma + Ollama)
    --port=PORT            Override backend port (default: 4040)

${CYAN}BUILD & TEST:${NC}
    ${BOLD}build${NC}  [--frontend|--extension|--all]  Build frontend + Chrome extension (default: both)
    ${BOLD}test${NC}   [pytest args]                   Run backend tests
    ${BOLD}lint${NC}                                   Run ruff linter

${CYAN}DATABASE:${NC}
    ${BOLD}db init${NC}                               Create tables (safe to re-run)
    ${BOLD}db reset${NC}                              Drop + recreate database (DESTRUCTIVE)
    ${BOLD}db migrate${NC}                            Run Alembic migrations
    ${BOLD}db shell${NC}                              Open psql or sqlite3 CLI

${CYAN}DOCKER SERVICES:${NC} ${DIM}(individual containers)${NC}
    ${BOLD}services up${NC}   [postgres meili chroma ollama all]
    ${BOLD}services down${NC}  [names...]
    ${BOLD}services status${NC}

${CYAN}DOCKER COMPOSE:${NC} ${DIM}(full deployment)${NC}
    ${BOLD}docker up${NC}                             Start full compose stack
    ${BOLD}docker down${NC}                           Stop compose stack
    ${BOLD}docker build${NC}                          Build Docker image
    ${BOLD}docker logs${NC}                           Tail compose logs
    ${BOLD}docker simple${NC}                         Minimal stack (SQLite only)

${CYAN}MAINTENANCE:${NC}
    ${BOLD}clean${NC}                                 Remove build artifacts, logs, caches
    ${BOLD}version${NC}                               Show version
    ${BOLD}help${NC}                                  Show this help

${CYAN}EXAMPLES:${NC}
    ./app.sh setup                          # First-time setup
    ./app.sh start                          # Start everything per .env
    ./app.sh start --sqlite                 # Quick start, no Docker
    ./app.sh start --postgres --prod        # Production with PostgreSQL
    ./app.sh start -b --port=8080           # Backend only on custom port
    ./app.sh stop                           # Stop all app services
    ./app.sh db reset                       # Reset database
    ./app.sh services up postgres meili     # Start specific Docker services
    ./app.sh docker up                      # Full Docker compose deployment
    ./app.sh logs worker                    # Tail worker logs
EOF
}

# ─── Main ────────────────────────────────────────────────────────

cd "$SCRIPT_DIR"

case "${1:-start}" in
    setup)
        shift 2>/dev/null || true
        do_setup "$@"
        ;;
    start)
        shift 2>/dev/null || true
        do_start "$@"
        ;;
    stop)
        shift 2>/dev/null || true
        case "${1:-all}" in
            --backend|-b)   stop_backend ;;
            --frontend|-f)  stop_frontend ;;
            --worker|-w)    stop_worker ;;
            *)              stop_all ;;
        esac
        ;;
    restart)
        shift 2>/dev/null || true
        case "${1:-all}" in
            --backend|-b)   stop_backend;  sleep 1; start_backend ;;
            --frontend|-f)  stop_frontend; sleep 1; start_frontend ;;
            --worker|-w)    stop_worker;   sleep 1; start_worker ;;
            *)
                stop_all
                sleep 1
                do_start "$@"
                ;;
        esac
        ;;
    status)
        do_status
        ;;
    logs)
        shift 2>/dev/null || true
        do_logs "${1:-backend}"
        ;;
    build)
        shift 2>/dev/null || true
        do_build "$@"
        ;;
    test)
        shift 2>/dev/null || true
        do_test "$@"
        ;;
    lint)
        do_lint
        ;;
    db)
        shift 2>/dev/null || true
        do_db "$@"
        ;;
    services)
        shift 2>/dev/null || true
        case "${1:-status}" in
            up|start)   shift 2>/dev/null || true; services_up "$@" ;;
            down|stop)  shift 2>/dev/null || true; services_down "$@" ;;
            status)     services_status ;;
            *)          echo "Usage: ./app.sh services [up|down|status] [service...]" ;;
        esac
        ;;
    docker)
        shift 2>/dev/null || true
        do_docker "$@"
        ;;
    clean)
        do_clean
        ;;
    version|-v|--version)
        echo "$APP_NAME v$VERSION"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
