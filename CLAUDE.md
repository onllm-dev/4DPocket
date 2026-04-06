# 4DPocket - Project Guide

## What is this?

Self-hosted AI-powered personal knowledge base. Save content from 17+ platforms, AI auto-tags/summarizes/connects it, find anything instantly.

## Stack

- **Backend**: FastAPI + SQLModel + Python 3.12+ (sync `def` handlers, NOT `async def`)
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS v4 + Lucide React icons
- **Database**: SQLite (default) / PostgreSQL
- **Search**: SQLite FTS5 (default) / Meilisearch + ChromaDB (semantic)
- **AI**: Ollama / Groq / NVIDIA / Custom (OpenAI or Anthropic-compatible) (NO litellm, NO langchain)
- **Auth**: PyJWT + bcrypt direct (NO passlib, NO python-jose)
- **HTTP**: httpx (backend), native fetch (frontend) (NO axios)
- **Background Jobs**: Huey (SQLite backend)
- **State**: TanStack Query (server) + Zustand (client)

## Commands

```bash
# Backend
uv sync --all-extras          # Install deps
uv run uvicorn fourdpocket.main:app --port 4040  # Run server
uv run pytest tests/ -x -q    # Run tests
make test                      # Run tests (alias)
make lint                      # ruff check

# Frontend (from frontend/)
pnpm install                   # Install deps
pnpm dev                       # Dev server on :5173
pnpm build                     # Production build (tsc + vite)

# Multi-user mode
FDP_AUTH__MODE=multi uv run uvicorn fourdpocket.main:app --port 4040
```

## Versioning

All three version files must stay in sync when bumping:
- `pyproject.toml` (backend)
- `frontend/package.json` (frontend)
- `extension/package.json` (Chrome extension)

## Project Structure

```
src/fourdpocket/
  api/          # FastAPI routers (19 files)
  models/       # SQLModel tables
  processors/   # 17 platform extractors (BaseProcessor + @register_processor)
  ai/           # Providers, tagger, summarizer, sanitizer
  search/       # FTS5, Meilisearch, ChromaDB semantic
  sharing/      # Share manager, permissions, feed manager
  workers/      # Huey tasks (fetcher, archiver, enrichment, rules engine)
  storage/      # Local file storage (user-scoped)

frontend/src/
  pages/        # 18 page components
  components/   # Layout, BookmarkCard, ShareDialog, CommandPalette
  hooks/        # TanStack Query hooks + keyboard shortcuts
  api/client.ts # fetch wrapper with auth + 401 redirect
```

## Key Patterns

- **Config**: pydantic-settings with `FDP_` env prefix. Admin panel overrides via `InstanceSettings.extra["ai_config"]`
- **AI config precedence**: .env defaults < admin panel overrides. User-level controls only preferences (auto_tag, auto_summarize)
- **Sync enrichment**: Items are AI-enriched inline if Huey worker is not running (tagging + summarization, skips embedding)
- **Login**: Accepts both email and username (OR query on User table)
- **User scoping**: Every query includes `WHERE user_id = current_user.id`
- **Processors**: `@register_processor` decorator, URL pattern matching, returns `ProcessorResult`
- **AI safety**: All user content sanitized via `ai/sanitizer.py` before LLM prompts
- **SSRF protection**: `_fetch_url()` blocks internal networks (127.x, 10.x, 172.16.x, 169.254.x)
- **Dark mode**: Tailwind v4 `@custom-variant dark` in globals.css
- **Theme**: Doraemon Blue `#0096C7`, bell yellow `#FCD34D`, dark bg `#0C1222`

## Don'ts

- Don't use `async def` for route handlers (SQLModel is sync)
- Don't use passlib, python-jose, axios, or litellm
- Don't pass user content unsanitized to LLM prompts
- Don't hardcode secrets - use `FDP_` env vars
- First registered user auto-becomes admin
