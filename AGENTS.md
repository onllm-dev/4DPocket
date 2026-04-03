# 4DPocket - Setup & Testing Guide

## Quick Start

### Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 18+ with pnpm
- Optional: Ollama (local AI), Docker (full stack)

### 1. Backend Setup

```bash
git clone https://github.com/onllm-dev/4DPocket.git
cd 4DPocket
uv sync --all-extras
```

### 2. Start Backend

```bash
# Single-user mode (no login)
uv run uvicorn fourdpocket.main:app --port 4040

# Multi-user mode (with auth)
FDP_AUTH__MODE=multi uv run uvicorn fourdpocket.main:app --port 4040
```

### 3. Frontend Setup

```bash
cd frontend
pnpm install
pnpm dev
```

App runs at http://localhost:5173, API at http://localhost:4040/docs

### 4. First User (Multi-User Mode)

First registered user auto-becomes admin:

```bash
curl -X POST http://localhost:4040/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","email":"admin@local","password":"admin1234","display_name":"Admin"}'
```

Login at http://localhost:5173/login with `admin@local` / `admin1234`

## Running Tests

```bash
# Backend (55+ tests, in-memory SQLite)
uv run pytest tests/ -x -q

# Frontend type check
cd frontend && pnpm build

# Lint
make lint
```

## Configuration

All via env vars with `FDP_` prefix. Key settings:

```bash
FDP_AUTH__MODE=single           # single (no login) or multi (JWT auth)
FDP_AI__CHAT_PROVIDER=ollama    # ollama, groq, or nvidia
FDP_SEARCH__BACKEND=sqlite      # sqlite (FTS5) or meilisearch
FDP_DATABASE__URL=sqlite:///data/4dpocket.db
```

See `.env.example` for full reference.

## Docker (Full Stack)

```bash
cp .env.example .env
docker compose up
```

Includes: app, worker, PostgreSQL, Meilisearch, ChromaDB, Ollama.

## Architecture Notes

- 17 content processors auto-detect platform from URL
- AI enrichment runs as Huey background task (sync fallback if worker unavailable)
- Search: FTS5 default (zero-config), upgrade to Meilisearch for typo tolerance
- Semantic search via ChromaDB + sentence-transformers embeddings
- All user data is scoped per-user. Sharing creates references, not copies.
- Rules engine executes on item creation (condition-action pattern)
- PWA with share target: share URLs from phone directly to 4DPocket
