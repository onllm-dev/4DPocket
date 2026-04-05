# Development Guide

Complete guide to running 4DPocket locally for development.

## Prerequisites

- **Python 3.12+**
- **uv** (Python package manager) — [install](https://docs.astral.sh/uv/getting-started/installation/)
- **Node.js 22+** with **pnpm** — [install](https://pnpm.io/installation)
- **Git**

Optional:
- **Docker** — for PostgreSQL, Meilisearch, ChromaDB, Ollama
- **Tesseract OCR** — for image text extraction (`brew install tesseract` / `apt install tesseract-ocr`)

## Quick Start (Zero Config)

The simplest way to get started — SQLite, no Docker, no external services:

```bash
git clone https://github.com/onllm-dev/4DPocket.git
cd 4DPocket

# Backend
uv sync --all-extras
make dev
# → Server running at http://localhost:4040

# Frontend (new terminal)
cd frontend
pnpm install
pnpm dev
# → Frontend running at http://localhost:5173
```

That's it. SQLite database, FTS5 search, single-user mode, no login required.

## Hybrid Setup (Source + Docker Services)

Run the app from source but use Docker for databases and services. This is the recommended development setup for a production-like environment.

### With PostgreSQL

```bash
# Start PostgreSQL only
docker run -d --name 4dp-postgres \
  -p 5432:5432 \
  -e POSTGRES_USER=4dp \
  -e POSTGRES_PASSWORD=4dp \
  -e POSTGRES_DB=4dpocket \
  -v 4dp-postgres:/var/lib/postgresql/data \
  postgres:16-alpine

# Run backend against PostgreSQL
FDP_DATABASE__URL=postgresql://4dp:4dp@localhost:5432/4dpocket \
FDP_AUTH__MODE=multi \
make dev
```

### With PostgreSQL + Meilisearch

```bash
# Start services
docker run -d --name 4dp-postgres \
  -p 5432:5432 \
  -e POSTGRES_USER=4dp -e POSTGRES_PASSWORD=4dp -e POSTGRES_DB=4dpocket \
  -v 4dp-postgres:/var/lib/postgresql/data \
  postgres:16-alpine

docker run -d --name 4dp-meili \
  -p 7700:7700 \
  -e MEILI_MASTER_KEY=devkey123 \
  -v 4dp-meili:/meili_data \
  getmeili/meilisearch:v1.12

# Run backend
FDP_DATABASE__URL=postgresql://4dp:4dp@localhost:5432/4dpocket \
FDP_SEARCH__BACKEND=meilisearch \
FDP_SEARCH__MEILI_URL=http://localhost:7700 \
FDP_SEARCH__MEILI_MASTER_KEY=devkey123 \
FDP_AUTH__MODE=multi \
make dev
```

### With Ollama (Local AI)

```bash
# If you already have Ollama installed locally:
ollama pull llama3.2

# Or via Docker:
docker run -d --name 4dp-ollama -p 11434:11434 -v 4dp-ollama:/root/.ollama ollama/ollama
docker exec 4dp-ollama ollama pull llama3.2

# Run backend with Ollama
FDP_AI__CHAT_PROVIDER=ollama \
FDP_AI__OLLAMA_URL=http://localhost:11434 \
FDP_AI__OLLAMA_MODEL=llama3.2 \
make dev
```

### With Cloud AI (Groq / NVIDIA / Custom)

No Docker needed — just set environment variables:

```bash
# Groq (fast cloud inference)
FDP_AI__CHAT_PROVIDER=groq \
FDP_AI__GROQ_API_KEY=gsk_your_key_here \
make dev

# NVIDIA
FDP_AI__CHAT_PROVIDER=nvidia \
FDP_AI__NVIDIA_API_KEY=nvapi-your_key_here \
make dev

# Any OpenAI-compatible API
FDP_AI__CHAT_PROVIDER=custom \
FDP_AI__CUSTOM_BASE_URL=https://api.together.xyz/v1 \
FDP_AI__CUSTOM_API_KEY=your_key \
FDP_AI__CUSTOM_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo \
make dev
```

## Background Worker

The Huey worker processes background tasks: content fetching, AI enrichment, media downloads, RSS feeds, and automation rules.

```bash
# Run worker (separate terminal)
uv run python -m huey.bin.huey_consumer fourdpocket.workers.huey --workers 2
```

Without the worker, AI enrichment runs inline (synchronous) when `FDP_AI__SYNC_ENRICHMENT=true` (default).

## Multi-User Mode

```bash
FDP_AUTH__MODE=multi make dev
```

First registered user automatically becomes admin. Subsequent users get the `user` role.

## Running Tests

```bash
make test           # Run all tests (fast, stops on first failure)
make test-cov       # Run with coverage report
make lint           # Ruff linting
make format         # Auto-format code

# Frontend
cd frontend
pnpm build          # TypeScript check + production build
pnpm lint           # ESLint
```

## Project Structure

```
4DPocket/
├── src/fourdpocket/           # Python backend
│   ├── api/                   # FastAPI routers (auth, items, notes, search, etc.)
│   ├── models/                # SQLModel database tables
│   ├── processors/            # 17 platform-specific content extractors
│   ├── ai/                    # AI providers, tagger, summarizer, sanitizer
│   ├── search/                # FTS5, Meilisearch, ChromaDB, hybrid RRF
│   ├── sharing/               # Share manager, permissions, feed manager
│   ├── workers/               # Huey background tasks
│   ├── storage/               # User-scoped file storage
│   ├── config.py              # pydantic-settings config (FDP_ env prefix)
│   ├── main.py                # FastAPI app entry point
│   └── db/session.py          # Database engine + session management
├── frontend/                  # React 19 + TypeScript + Vite
│   └── src/
│       ├── pages/             # Page components
│       ├── components/        # Reusable UI components
│       ├── hooks/             # TanStack Query hooks
│       ├── stores/            # Zustand stores
│       └── api/client.ts      # API client (fetch wrapper)
├── extension/                 # Chrome browser extension (WXT)
├── tests/                     # pytest tests
├── Dockerfile                 # Multi-stage production build
├── docker-compose.yml         # Full stack (PostgreSQL, optional services)
├── docker-compose.simple.yml  # Minimal (SQLite only)
├── pyproject.toml             # Python project config
├── Makefile                   # Development commands
└── .env.example               # Configuration reference
```

## Configuration Reference

All configuration is via environment variables with the `FDP_` prefix. See [`.env.example`](.env.example) for the full list.

| Variable | Default | Description |
|----------|---------|-------------|
| `FDP_DATABASE__URL` | `sqlite:///./data/4dpocket.db` | Database URL (SQLite or PostgreSQL) |
| `FDP_AUTH__MODE` | `single` | `single` (no login) or `multi` (JWT auth) |
| `FDP_AUTH__SECRET_KEY` | auto-generated | JWT signing key (set in production) |
| `FDP_SEARCH__BACKEND` | `sqlite` | `sqlite` (FTS5) or `meilisearch` |
| `FDP_AI__CHAT_PROVIDER` | `ollama` | `ollama`, `groq`, `nvidia`, or `custom` |
| `FDP_AI__AUTO_TAG` | `true` | Enable AI auto-tagging |
| `FDP_AI__AUTO_SUMMARIZE` | `true` | Enable AI auto-summarization |
| `FDP_AI__SYNC_ENRICHMENT` | `true` | Run AI inline if no worker running |
| `FDP_STORAGE__BASE_PATH` | `./data` | Data directory path |
| `FDP_SERVER__PORT` | `4040` | Server port |
| `FDP_SERVER__SECURE_COOKIES` | `false` | Set `true` behind HTTPS |

## Chrome Extension

```bash
cd extension
pnpm install
pnpm dev       # Development with hot reload
pnpm build     # Production build
```

Load `extension/dist/chrome-mv3` as unpacked extension in `chrome://extensions`.

## Troubleshooting

**Port already in use:**
```bash
lsof -i :4040 | grep LISTEN   # Find the process
kill -9 <PID>                   # Kill it
```

**Database issues:**
```bash
# Reset SQLite (delete and restart)
rm -rf data/4dpocket.db*
make dev

# PostgreSQL: drop and recreate
docker exec 4dp-postgres psql -U 4dp -c "DROP DATABASE 4dpocket; CREATE DATABASE 4dpocket;"
```

**Frontend not connecting to backend:**
The Vite dev server proxies `/api` to `localhost:4040`. Make sure the backend is running first.

**AI not working:**
Check `GET /api/v1/ai/status` — it shows the configured provider and whether it's reachable.
