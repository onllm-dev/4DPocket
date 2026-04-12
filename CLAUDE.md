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
- **MCP**: FastMCP streamable-HTTP server mounted at `/mcp` (inner `streamable_http_path="/"` + 307 redirect so both `/mcp` and `/mcp/` work); PAT-validated `TokenVerifier`; 10 tools (persist/recall/navigate/update/delete)
- **HTTP**: httpx (backend), native fetch (frontend) (NO axios)
- **Background Jobs**: Huey (SQLite backend) — stage-based enrichment pipeline
- **State**: TanStack Query (server) + Zustand (client)

## Commands

```bash
# Backend
uv sync --all-extras          # Install deps
uv run uvicorn fourdpocket.main:app --port 4040  # Run server
uv run pytest tests/ -x -q    # Run tests (183 tests)
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
  api/          # FastAPI routers (26 files, including entities)
  models/       # SQLModel tables (26 tables: items, chunks, entities, relations, enrichment, LLM cache, ...)
  processors/   # 17 platform extractors (BaseProcessor + @register_processor)
  ai/           # Providers, tagger, summarizer, extractor, canonicalizer, LLM cache, sanitizer
  search/       # SearchService + pluggable backends
    service.py          # Orchestrator: keyword + vector + RRF + optional rerank
    base.py             # Protocols: KeywordBackend, VectorBackend, Reranker
    backends/           # sqlite_fts, chroma, pgvector, meilisearch
    chunking.py         # Content chunking (paragraph/sentence/word, 512 tokens, 64 overlap)
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
