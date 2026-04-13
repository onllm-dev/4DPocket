# 4DPocket - Project Guide

## What is this?

Self-hosted AI-powered personal knowledge base. Save content from 17+ platforms, AI auto-tags/summarizes/connects it, find anything instantly.

## Stack

- **Backend**: FastAPI + SQLModel + Python 3.12+ (sync `def` handlers, NOT `async def`)
- **Frontend**: React 19 + TypeScript + Vite + Tailwind CSS v4 + Lucide React icons + React Flow (graph)
- **Database**: SQLite (default) / PostgreSQL (with pgvector)
- **Search**: SearchService with pluggable backends — SQLite FTS5 / Meilisearch (keyword) + ChromaDB / pgvector (vector) + RRF fusion + optional cross-encoder reranking
- **AI**: Ollama / Groq / NVIDIA / Custom (OpenAI or Anthropic-compatible) (NO litellm, NO langchain)
- **Auth**: PyJWT + bcrypt direct (NO passlib, NO python-jose); **PATs** (`fdp_pat_*`) alongside JWT
- **MCP**: FastMCP streamable-HTTP server mounted at `/mcp` (inner `streamable_http_path="/"` + 307 redirect so both `/mcp` and `/mcp/` work); PAT-validated `TokenVerifier`; 11 tools (persist/recall/navigate/update/delete, incl. `search_in_collection`)
- **HTTP**: httpx (backend) + curl_cffi for TLS impersonation (Medium), native fetch (frontend) (NO axios)
- **Background Jobs**: Huey (SQLite backend) — stage-based enrichment pipeline
- **State**: TanStack Query (server) + Zustand (client)

## Commands

All lifecycle operations go through `./app.sh` — single entry point that handles processes, ports, PID/log files, Huey worker, and Docker services.

```bash
# Setup (first time)
./app.sh setup                 # Install deps, build frontend, create .env
./app.sh setup --deps          # Also install system packages (Python, Node, etc.)

# Lifecycle
./app.sh start                 # Start backend + frontend + worker (reads .env)
./app.sh start --sqlite        # Zero-config start (SQLite, no Docker)
./app.sh start --postgres      # PostgreSQL + Meilisearch (auto-starts Docker)
./app.sh start --full          # Full stack (+ ChromaDB + Ollama)
./app.sh start -b              # Backend only (-f frontend, -w worker)
./app.sh stop                  # Stop all (or --backend / --frontend / --worker)
./app.sh restart               # Restart all (or --backend / --frontend / --worker)
./app.sh status                # Service + Docker + .env summary
./app.sh logs [backend|frontend|worker|all]

# Test, lint, build
./app.sh test                  # uv run pytest tests/ -x -q (forwards extra args)
./app.sh lint                  # ruff check src/ tests/
./app.sh build                 # Build frontend + Chrome extension (default: both)
./app.sh build --frontend      # Frontend only (--extension for extension only)

# Database
./app.sh db init               # Create tables (safe to re-run)
./app.sh db reset              # Drop + recreate (DESTRUCTIVE, prompts)
./app.sh db migrate            # Alembic upgrade head
./app.sh db shell              # Open psql or sqlite3

# Docker services (individual containers)
./app.sh services up [postgres meili chroma ollama all]
./app.sh services down [names...]
./app.sh services status

# Docker compose (full deployment)
./app.sh docker up | down | build | logs | simple

# Maintenance
./app.sh clean                 # Remove build artifacts, logs, caches
./app.sh help                  # Full help

# Multi-user mode (env override before start)
FDP_AUTH__MODE=multi ./app.sh start
```

### Direct tool fallbacks

For ad-hoc workflows that bypass `app.sh` (custom uvicorn flags, single-test selection, etc.):

```bash
uv sync --all-extras
uv run uvicorn fourdpocket.main:app --port 4040
uv run pytest tests/ -x -q
cd frontend && pnpm dev       # Dev server on :5173
cd frontend && pnpm build     # tsc + vite
```

## Versioning

All three version files must stay in sync when bumping:
- `pyproject.toml` (backend)
- `frontend/package.json` (frontend)
- `extension/package.json` (Chrome extension)

## Project Structure

```
src/fourdpocket/
  api/          # FastAPI routers (26 files, including entities)
  models/       # SQLModel tables (26 tables: items, chunks, entities, relations, enrichment, LLM cache, ...)
  processors/   # 17 platform extractors (BaseProcessor + @register_processor)
  ai/           # Providers, tagger, summarizer, extractor, canonicalizer, LLM cache, sanitizer
  search/       # SearchService + pluggable backends
    service.py          # Orchestrator: keyword + vector + RRF + optional rerank
    base.py             # Protocols: KeywordBackend, VectorBackend, Reranker
    backends/           # sqlite_fts, chroma, pgvector, meilisearch
    chunking.py         # Section-aware chunking with provenance (kind, author, heading_path)
    reranker.py         # NullReranker + LocalReranker (cross-encoder)
    filters.py          # Inline filter syntax parser
  sharing/      # Share manager, permissions, feed manager
  workers/      # Huey tasks
    enrichment_pipeline.py  # Stage-based: chunked→embedded→tagged→summarized→entities_extracted
    fetcher.py              # URL content extraction
    ai_enrichment.py        # Legacy enrichment (deprecated, kept for backward compat)
  storage/      # Local file storage (user-scoped)

frontend/src/
  pages/        # 22 page components
  components/   # Layout, BookmarkCard, ShareDialog, CommandPalette
  hooks/        # TanStack Query hooks + keyboard shortcuts
  api/client.ts # fetch wrapper with auth + 401 redirect
```

## Search Architecture

```
Query → KeywordBackend.search() → ┐
                                   ├→ RRF Fusion (k=60) → Reranker (optional) → Results
Query → embed → VectorBackend.search() → ┘
```

- **Auto-detection**: `vector_backend=auto` picks pgvector for Postgres, ChromaDB for SQLite
- **Chunk-level**: Content split into overlapping chunks, indexed in both keyword + vector backends
- **Fallback**: Chunk search → item-level search if no chunks exist
- **pgvector dimensions**: Auto-detected from embedding provider (not hardcoded)

## Enrichment Pipeline

```
Item Created → enrich_item_v2()
  ├─ chunked (independent)     → chunk content → index in FTS + vector
  ├─ tagged (independent)      → AI auto-tagging
  └─ summarized (independent)  → AI summary
       ├─ embedded (depends: chunked)           → per-chunk embeddings
       └─ entities_extracted (depends: chunked)  → entity + relation extraction
```

- Each stage tracked in `enrichment_stages` table with status, attempts, errors
- LLM responses cached in `llm_cache` table by content hash
- Entity extraction uses gleaning (multi-pass) to catch missed entities
- Entities canonicalized via 3-tier matching (exact alias → normalized name → create new)

## PATs + MCP

- **Tokens**: `api_tokens` + `api_token_collections`. Format `fdp_pat_<6>_<43>`; sha256 stored, `hmac.compare_digest` on lookup
- **ACL flags**: `role` (viewer|editor), `all_collections`, `collection_ids`, `include_uncollected`, `allow_deletion`, `admin_scope`, `expires_at`
- **Resolver**: `api/deps.py:_resolve_identity` detects `Bearer fdp_pat_...` and routes through `api_token_utils.resolve_token`; falls back to JWT otherwise
- **Admin guard**: `require_admin` rejects PATs without `admin_scope=True` even when owner is admin
- **MCP tools** (`src/fourdpocket/mcp/tools.py`): `save_knowledge`, `search_knowledge`, `get_knowledge`, `update_knowledge`, `refresh_knowledge`, `delete_knowledge` (gated by `allow_deletion`), `list_collections`, `add_to_collection`, `get_entity`, `get_related_entities`. Tool param name is `knowledge_id` (not `item_id`). Delete uses shared `cascade_delete_item()` helper in `api/items.py`.
- **Synthesis**: per-entity structured JSON (`summary`, `themes`, `key_contexts`, `relationships`, `confidence`) regenerated when `item_count - synthesis_item_count >= threshold` AND `min_interval_hours` elapsed. Config: `FDP_ENRICHMENT__SYNTHESIS_*`

## Key Patterns

- **Config**: pydantic-settings with `FDP_` env prefix. Admin panel overrides via `InstanceSettings.extra["ai_config"]`
- **AI config precedence**: .env defaults < admin panel overrides. User-level controls only preferences (auto_tag, auto_summarize)
- **Sync enrichment**: Items are AI-enriched inline if Huey worker is not running (tagging + summarization, skips embedding)
- **Login**: Accepts both email and username (OR query on User table)
- **User scoping**: Every query includes `WHERE user_id = current_user.id`
- **Processors**: `@register_processor` decorator, URL pattern matching, returns `ProcessorResult`
- **AI safety**: All user content sanitized via `ai/sanitizer.py` before LLM prompts
- **SSRF protection**: `_fetch_url()` blocks internal networks (127.x, 10.x, 172.16.x, 169.254.x)
- **Search backends**: Protocol-based (`KeywordBackend`, `VectorBackend`), lazy singleton via `get_search_service()`
- **Entity canonicalization**: 3-tier matching with description merging across documents
- **Dark mode**: Tailwind v4 `@custom-variant dark` in globals.css
- **Theme**: Doraemon Blue `#0096C7`, bell yellow `#FCD34D`, dark bg `#0C1222`

## Don'ts

- Don't use `async def` for route handlers (SQLModel is sync)
- Don't use passlib, python-jose, axios, or litellm
- Don't pass user content unsanitized to LLM prompts
- Don't hardcode secrets - use `FDP_` env vars
- Don't hardcode embedding dimensions - use auto-detection
- First registered user auto-becomes admin
