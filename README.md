<p align="center">
  <img src="frontend/public/icons/icon-192.png" width="96" alt="4DPocket" />
</p>

<h1 align="center">4DPocket</h1>

<p align="center">
  <em>"Reach into your pocket and pull out exactly what you need."</em>
</p>

<p align="center">
  <strong>Self-hosted, AI-powered personal knowledge base</strong><br/>
  Save content from 17+ platforms. AI auto-tags, summarizes, and connects it. Find anything instantly.
</p>

<p align="center">
  <a href="https://github.com/onllm-dev/4DPocket/releases/latest"><img src="https://img.shields.io/github/v/release/onllm-dev/4DPocket?label=release&color=blue" alt="Latest Release" /></a>
  <a href="https://pypi.org/project/4dpocket/"><img src="https://img.shields.io/pypi/v/4dpocket?color=blue&logo=pypi&logoColor=white" alt="PyPI" /></a>
  <a href="https://github.com/onllm-dev/4DPocket/pkgs/container/4dpocket"><img src="https://img.shields.io/badge/ghcr.io-4dpocket-blue?logo=docker" alt="Docker Image" /></a>
  <img src="https://img.shields.io/badge/python-3.12+-blue" alt="Python 3.12+" />
  <img src="https://img.shields.io/badge/react-19-61DAFB" alt="React 19" />
  <img src="https://img.shields.io/badge/license-GNU%20GPLv3-blue" alt="GNU GPLv3 License" />
  <a href="https://github.com/onllm-dev/4DPocket/actions/workflows/ci.yml"><img src="https://github.com/onllm-dev/4DPocket/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
</p>

<p align="center">
  <a href="https://github.com/onllm-dev/4DPocket">GitHub</a> &middot; <a href="https://onllm.dev">onllm.dev</a> &middot; <a href="https://buymeacoffee.com/prakersh">Support 4DPocket</a>
</p>

---

## Why 4DPocket?

Everyone saves things — bookmarks, articles, videos, code snippets, social posts — across dozens of platforms. Then can never find them again.

**4DPocket** is not a bookmark manager. It's a **knowledge base that thinks**. Paste a URL — the system extracts the full content, auto-tags it, generates a summary, connects it to what you already know, and makes it instantly searchable. Notes, highlights, collections, reading lists, RSS feeds, and automation rules turn it into a second brain.

Inspired by Doraemon's 4D Pocket — a magical, bottomless pocket where anything you've ever saved is instantly retrievable.

| Principle | What It Means |
|-----------|--------------|
| **Knowledge-First** | Every item is extracted, enriched, indexed, and connected |
| **Retrieval-First** | Search is instant, fuzzy, semantic, and forgiving |
| **Local-First** | Runs entirely on your machine. Your data never leaves |
| **Zero-Friction** | Save anything in 1-2 actions. AI handles organization |
| **Private by Default** | Per-user isolation. Sharing is explicit and revocable |

---

## Quick Start

### Docker (Recommended)

Pull the image from GitHub Container Registry:

```bash
docker pull ghcr.io/onllm-dev/4dpocket:latest
# or a specific version:
docker pull ghcr.io/onllm-dev/4dpocket:0.2.0
```

**One-liner (SQLite, no external services):**
```bash
docker run -d --name 4dpocket -p 4040:4040 -v 4dp-data:/data \
  ghcr.io/onllm-dev/4dpocket:latest
```

Open http://localhost:4040 — no login needed in single-user mode.

### Docker Compose

**Full stack** (PostgreSQL + background worker):

```bash
# Clone or download config files
curl -O https://raw.githubusercontent.com/onllm-dev/4DPocket/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/onllm-dev/4DPocket/main/.env.example
cp .env.example .env     # Edit with your settings

# Start
docker compose up -d
```

Open http://localhost:4040 — first registered user becomes admin.

**Minimal setup** (SQLite, single container):
```bash
curl -O https://raw.githubusercontent.com/onllm-dev/4DPocket/main/docker-compose.simple.yml
docker compose -f docker-compose.simple.yml up -d
```

**With local AI (Ollama):**
```bash
docker compose --profile ai up -d
docker compose exec ollama ollama pull llama3.2
```

**With Meilisearch (full-text search):**
```bash
SEARCH_BACKEND=meilisearch docker compose --profile search up -d
```

**With semantic search (ChromaDB):**
```bash
docker compose --profile vectors up -d
```

**All services:**
```bash
docker compose --profile ai --profile search --profile vectors up -d
```

### Python Package (PyPI)

Available on [PyPI](https://pypi.org/project/4dpocket/):

```bash
pip install 4dpocket

# First-time setup wizard (database, AI provider, auth mode)
4dpocket setup

# Start the server
4dpocket start

# Or start with a specific profile:
4dpocket start --sqlite              # Zero-config, no Docker needed
4dpocket start --postgres            # PostgreSQL + Meilisearch (auto-starts Docker)
4dpocket start --full                # Full stack (+ ChromaDB + Ollama)

# Background (daemon) mode
4dpocket start --sqlite -d
```

Open http://localhost:4040 — the setup wizard runs automatically on first start if no config exists.

> **Note:** The PyPI package name is `4dpocket`, but the Python import is `fourdpocket` (Python identifiers can't start with a digit). Optional extras: `pip install 4dpocket[postgres]`, `4dpocket[semantic]`, `4dpocket[processors]`, `4dpocket[all]`.

### From Source (uv)

```bash
git clone https://github.com/onllm-dev/4DPocket.git
cd 4DPocket

# Backend
uv sync --all-extras
make dev                    # → http://localhost:4040

# Or via CLI
4dpocket start --reload     # → http://localhost:4040

# Frontend (separate terminal)
cd frontend && pnpm install && pnpm dev   # → http://localhost:5173
```

No login needed in single-user mode.

### Hybrid (Source + Docker Services)

Run the app from source while using Docker for PostgreSQL, Meilisearch, or Ollama:

```bash
# Start PostgreSQL with pgvector (enables vector search without ChromaDB)
docker run -d --name 4dp-postgres -p 5432:5432 \
  -e POSTGRES_USER=4dp -e POSTGRES_PASSWORD=4dp -e POSTGRES_DB=4dpocket \
  pgvector/pgvector:pg16

# Run backend against PostgreSQL with multi-user auth
FDP_DATABASE__URL=postgresql://4dp:4dp@localhost:5432/4dpocket \
FDP_AUTH__MODE=multi make dev
```

Add Meilisearch, Ollama, ChromaDB, or cloud AI — see the [Development Guide](DEVELOPMENT.md) for all combinations.

### Multi-User Mode

```bash
FDP_AUTH__MODE=multi make dev
```

First registered user automatically becomes admin.

---

## CLI Reference

The `4dpocket` command provides full lifecycle management — setup, start/stop, database, Docker services, and maintenance.

```
4dpocket setup                       Interactive first-run wizard
4dpocket start [--sqlite|--postgres|--full]  Start server with profile
4dpocket start -d                    Start in background (daemon mode)
4dpocket stop                        Stop background server
4dpocket restart                     Restart server
4dpocket status                      Show server + Docker service status
4dpocket logs                        Tail server logs

4dpocket db init                     Create database tables
4dpocket db reset [-y]               Drop + recreate database (destructive)
4dpocket db migrate                  Run Alembic migrations
4dpocket db shell                    Open psql or sqlite3 CLI

4dpocket services up [postgres meili chroma ollama all]
4dpocket services down [names...]
4dpocket services status

4dpocket clean                       Remove logs, PID files, caches
4dpocket version                     Show version
```

The setup wizard configures database (SQLite/PostgreSQL), AI provider (Ollama/Groq/NVIDIA/Custom/None), auth mode, and server port. Configuration is saved to `~/.4dpocket/.env`.

Start profiles auto-manage Docker containers — `--postgres` starts PostgreSQL + Meilisearch, `--full` adds ChromaDB + Ollama. No manual `docker run` needed.

---

## Using 4DPocket as an MCP Server

4DPocket ships a built-in **Model Context Protocol** server at `/mcp`, letting Claude Desktop, Cursor, Claude Code, Codex, and any other MCP-capable agent use your knowledge base as **persistent memory**.

Ten tools are exposed, covering the full persist-recall-navigate-update-delete cycle:

| Tool | Purpose |
|---|---|
| `save_knowledge` | Save a URL or paste raw content — triggers enrichment |
| `search_knowledge` | Chunk-level hybrid search (keyword + semantic + RRF + rerank) |
| `get_knowledge` | Full detail for a single item (content, tags, entities, collections) |
| `update_knowledge` | Edit title/content/tags/favorite/archived |
| `refresh_knowledge` | Re-run enrichment pipeline for an item |
| `delete_knowledge` | Hard-delete (requires `allow_deletion` token flag) |
| `list_collections` | Enumerate collections the token can access |
| `add_to_collection` | Organize saved items |
| `get_entity` | Fetch entity detail including LLM-authored synthesis |
| `get_related_entities` | Follow associative trails in the concept graph |

### 1. Create a Personal Access Token

In the app: **Settings → API Tokens & MCP → New token**. Choose:
- **Role:** `viewer` (read-only) or `editor` (read + write)
- **Access:** All collections, or specific collections (plus optional "uncollected items" toggle)
- **Allow deletion:** optional, editor-only
- **Admin scope:** optional, admins only — gates `/api/v1/admin/*`
- **Expiry:** Never / 30d / 90d / 1 year / 2 years

The plaintext token is shown **once**. Copy it immediately — it's stored only as a sha256 hash.

### 2. Wire an MCP client

**Claude Desktop** — `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "4dpocket": {
      "url": "http://localhost:4040/mcp",
      "headers": { "Authorization": "Bearer fdp_pat_..." }
    }
  }
}
```

**Cursor** — `~/.cursor/mcp.json` (same shape as above).

**Claude Code / Codex / other** — use the Raw JSON template from the Settings page.

**Stdio-only clients** — if your client can't speak streamable HTTP directly, use the published npm launcher [`@onllm-dev/4dpocket-mcp`](https://www.npmjs.com/package/@onllm-dev/4dpocket-mcp):

```json
{
  "mcpServers": {
    "4dpocket": {
      "command": "npx",
      "args": ["-y", "@onllm-dev/4dpocket-mcp",
               "--url", "https://your.pocket.tld",
               "--token", "fdp_pat_..."]
    }
  }
}
```

### 3. Use it

Ask your agent things like:
- *"Save this article to my 'research' collection."*
- *"What did I save last month about FastAPI?"*
- *"Show me everything related to the 'async patterns' concept."*
- *"Regenerate the synthesis for the Postgres entity."*

Collection-scoped tokens only return items the user authorized. Viewer tokens cannot call write tools. Admin endpoints reject PATs without `admin_scope`.

### Entity synthesis — the Karpathy wiki pattern

Each entity accumulates an LLM-authored structured synthesis as more items mention it. Regeneration is automatic (after 3+ mentions, throttled to once per 24h) or manual via `POST /api/v1/entities/{id}/synthesize?force=true` / the Regenerate button in the UI. Visualize the full concept graph at **Knowledge Graph** in the sidebar.

---

## Features

### Universal Capture — 17 Platform Processors

Paste a URL and 4DPocket detects the platform, deeply extracts content, and enriches it with AI — all automatically.

| Platform | What's Extracted |
|----------|-----------------|
| **Generic URL** | Title, description, full article (readability), OG metadata, favicon |
| **YouTube** | Title, channel, duration, full transcript, chapters, thumbnails |
| **Reddit** | Post, selftext, top 10 comments, subreddit, score, crosspost info |
| **GitHub** | Repo metadata, README, stars, language, issues/PRs with comments, gists |
| **Twitter/X** | Tweet text, author, media, engagement stats (via fxtwitter API) |
| **Instagram** | Caption, images/carousel, hashtags, alt text |
| **Hacker News** | Title, author, score, threaded comments (via Algolia API) |
| **Stack Overflow** | Question, accepted answer, top answers, tags, code blocks |
| **TikTok** | Description, author, thumbnail, hashtags, view count |
| **Mastodon** | Toot content, media, boosts, favourites (auto-detects instance) |
| **Threads** | Author, content, media |
| **Substack** | Full article, author, newsletter name |
| **Medium** | Full article via JSON API + readability fallback |
| **LinkedIn** | Post text, author (public posts) |
| **Spotify** | Track/album/playlist, artist, cover art (oEmbed) |
| **Image** | EXIF data, OCR text extraction |
| **PDF** | Full text, metadata, page count |

### AI-Powered Organization

| Feature | Description |
|---------|-------------|
| **Auto-Tagging** | AI reads content and assigns tags with confidence scores. High-confidence tags applied automatically |
| **Auto-Summarization** | Every item gets a 2-3 sentence AI summary |
| **Entity Extraction** | AI extracts people, organizations, tools, concepts, and locations from content with a gleaning pass to catch missed entities |
| **Concept Graph** | Extracted entities are linked by relationships — browse connections between ideas across your knowledge base |
| **Entity Canonicalization** | Deduplicates entities across documents (e.g., "JS" and "JavaScript" → same entity). Merges descriptions from multiple sources |
| **AI Title Generation** | Generate better titles for notes and items |
| **Content Refresh** | Re-fetch and reprocess any item from its source URL. Manual tags, notes, and collections stay intact |
| **Related Items** | Semantic similarity (0.5) + shared tags (0.3) + same-source (0.2) |
| **Knowledge Gap Analysis** | AI identifies topics you've been collecting but lack depth in |
| **Cross-Platform Insights** | Discover connections between content saved from different platforms |
| **Smart Collection Suggestions** | AI suggests which collection an item belongs in |
| **Stale Content Detection** | Surface items that may need revisiting or updating |
| **Voice Transcription** | Transcribe audio recordings to text |
| **LLM Response Caching** | Extraction and enrichment results cached by content hash — avoids redundant LLM calls on retries |
| **Prompt Injection Protection** | Content sanitized before AI — homoglyph normalization, URL-decode, zero-width stripping |

**Multi-Provider AI** — Ollama (local), Groq, NVIDIA, or any OpenAI/Anthropic-compatible API. No vendor lock-in.

### Enrichment Pipeline

Every saved item goes through a stage-based enrichment pipeline with dependency tracking, retry support, and per-stage status monitoring:

```
Item Created
  ├─ chunked     → Split content into overlapping chunks
  ├─ tagged      → AI auto-tagging with confidence scores
  └─ summarized  → AI summary generation
       │
       ├─ embedded           → Generate embeddings (depends on: chunked)
       └─ entities_extracted → Extract entities + relations (depends on: chunked)
```

Independent stages run in parallel. Dependent stages auto-enqueue when prerequisites complete. Failed stages can be retried (up to 3 attempts). Monitor progress via `GET /items/{id}/enrichment`.

### Search & Retrieval — Chunk-Level Hybrid Pipeline

4DPocket uses a multi-stage retrieval architecture inspired by [LightRAG](https://github.com/HKUDS/LightRAG), combining keyword search, vector similarity, and optional cross-encoder reranking for production-grade search quality.

**Architecture:**

```
Query → Keyword Backend → ┐
                          ├→ RRF Fusion → Reranker (optional) → Results
Query → Vector Backend  → ┘
```

| Stage | How It Works |
|-------|-------------|
| **Chunking** | Content split into overlapping chunks (512 tokens, 64 overlap) at paragraph/sentence boundaries. Each chunk indexed independently for paragraph-level precision |
| **Keyword Search** | SQLite FTS5 (BM25, porter stemming) or Meilisearch — searches both item-level and chunk-level indexes |
| **Vector Search** | Sentence-transformers embeddings stored in ChromaDB (SQLite) or pgvector (Postgres). Chunk-level + item-level embeddings |
| **RRF Fusion** | Reciprocal Rank Fusion (k=60) merges keyword + vector results, deduplicates by item |
| **Reranking** | Optional cross-encoder (`ms-marco-MiniLM-L-6-v2`) re-scores top candidates for precision |
| **Unified Search** | Returns items AND notes together with inline filter syntax |

**Backend abstraction** — pluggable `KeywordBackend` and `VectorBackend` protocols:

| Deployment | Keyword Backend | Vector Backend |
|-----------|----------------|---------------|
| **SQLite** (default) | SQLite FTS5 | ChromaDB |
| **PostgreSQL** | Meilisearch | pgvector (HNSW index, auto-detected dimensions) |

**Search modes:** Full-text, fuzzy fallback, semantic, hybrid (RRF), unified (items + notes). Inline filter syntax: `docker tag:devops is:favorite after:2024-01`. All 7 filter types supported across all backends.

### Notes

Full-featured note-taking with a rich text editor (Tiptap).

- Create, edit, and organize notes alongside saved items
- Rich text editing — headings, bold, italic, strikethrough, code, lists, task lists, blockquotes, highlights
- Tag notes independently, search them alongside items
- AI summarization and title generation per note
- Highlights can link to notes (not just items)
- Notes appear in collections, knowledge base, and unified search

### Reading List & Progress Tracking

- **Reading List** — Dedicated "To Read" and "Read" tabs for managing your reading queue
- **Reading Progress** — Track reading progress (percentage) on any item
- **Reading Status** — Items move through `unread` → `reading` → `read`
- **Timeline View** — Browse your knowledge base chronologically

### Collections

- Create named collections to organize items and notes
- Add items and notes to multiple collections
- Drag-and-drop reorder within collections
- **Smart Items** — AI suggests items that belong in a collection based on its contents
- **Collection RSS** — Every collection exposes an RSS feed for external consumption

### Highlights & Annotations

- Highlight text within items or notes with color options
- Add annotation notes to highlights
- Position tracking (paragraph, sentence, start, end)
- Search across all highlights
- Chrome extension captures highlights directly from web pages

### RSS Feed Management

- Subscribe to RSS/Atom/JSON feeds
- **Auto mode** — New entries automatically saved to your knowledge base
- **Approval mode** — Entries queued for manual approve/reject
- Keyword filters per feed
- Manual fetch trigger, error tracking, entry management

### Automation Rules

- **Condition-Action rules** — "If URL matches `reddit.com`, auto-tag `reddit` and add to collection"
- Conditions: URL regex, source platform, title/content keywords, has tag
- Actions: add tag, add to collection, set favorite, archive
- ReDoS-safe regex execution with cross-platform timeout

### Sharing & Collaboration

- **Share items, collections, or tag groups** with specific users
- **Public links** — Generate public URLs with optional expiry
- **Roles** — Viewer or editor per share recipient
- **Comments** — Discuss shared items with collaborators
- **Knowledge Feed** — Follow other users' shared content
- **Shared With Me** — View all content shared to you

### Import & Export

| Direction | Formats |
|-----------|---------|
| **Import** | Chrome bookmarks (HTML), Pocket export (HTML), JSON |
| **Export** | JSON, HTML bookmarks (Netscape), CSV, Markdown |

URL validation on import, content size caps (1MB content, 50K description), XSS-safe HTML export.

### Admin Panel

- **User Management** — List, activate/deactivate, change roles, delete users (with full cascade cleanup)
- **Registration Control** — Toggle open/invite/disabled, set max users
- **AI Configuration** — Change provider, API keys, model, base URL at runtime. Admin settings override `.env`
- **Instance Settings** — Name, default role, feature toggles

### Saved Filters

- Save complex search/filter combinations for quick re-use
- Execute saved filters with one click
- Full CRUD management

### Tag Management

- Full CRUD with slug generation
- **Tag Merge** — Merge duplicate tags, combining their usage counts
- **Merge Suggestions** — AI suggests similar tags that could be consolidated
- Usage count tracking (auto-maintained on item/note add/remove)
- Browse items by tag

---

## Security

4DPocket is hardened for self-hosted production deployment:

| Protection | Implementation |
|------------|---------------|
| **Authentication** | JWT (HS256 hardcoded) + httpOnly strict-SameSite cookies |
| **Rate Limiting** | Database-backed (shared across workers), escalating lockout |
| **SSRF Protection** | Per-hop redirect validation on all 17 processors + RSS + media downloads |
| **DNS Rebinding** | IP pinning on media downloads |
| **XSS Prevention** | DOMPurify on all HTML render + write paths, HTML stripping on comments/highlights |
| **AI Safety** | Prompt injection filtering, homoglyph normalization, URL-decode, zero-width stripping |
| **Input Validation** | Pydantic `extra="forbid"` on create schemas, content size caps, URL scheme rejection |
| **Password Security** | bcrypt + constant-time dummy hash (prevents user enumeration) |
| **Foreign Keys** | SQLite FK enforcement via PRAGMA |
| **Security Headers** | X-Content-Type-Options, X-Frame-Options, CSP |
| **Storage Safety** | Path traversal protection, user-scoped file storage |

---

## PWA & Chrome Extension

### Progressive Web App

- Installable on Android, iOS, desktop
- Service worker caches static assets for offline access
- Share Target — share URLs from your phone's share sheet directly to 4DPocket
- Responsive — mobile (bottom nav), tablet (collapsible sidebar), desktop (full sidebar + shortcuts)
- Dark mode — system-aware with manual toggle (Doraemon Blue theme)

### Chrome Extension (Beta)

Save pages with one click, highlight text on any page, view highlights in a sidebar. Currently in beta — tested with Google Chrome.

**Install from release:** Download `4dpocket-chrome-extension-*.zip` from the [latest release](https://github.com/onllm-dev/4DPocket/releases/latest), unzip, load in `chrome://extensions` (Developer mode > Load unpacked).

**Build from source:**
```bash
./app.sh build                    # builds frontend + extension together
./app.sh build --extension        # extension only
# or manually: cd extension && pnpm install && pnpm build
```
Load `extension/dist/chrome-mv3` as an unpacked extension in `chrome://extensions` (Developer mode → Load unpacked). `./app.sh setup` also installs extension dependencies and produces this build out of the box.

- One-click save current page
- Right-click context menu save
- Auto-detect already-saved pages (badge indicator)
- Text highlight capture with floating tooltip
- Side panel for browsing highlights

### Keyboard Shortcuts

- `Cmd+K` / `Ctrl+K` — Command palette (search, navigate, quick actions)
- `n` — Add new item
- `/` — Focus search
- Bulk select + bulk tag/archive/delete

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI, SQLModel, Python 3.12+ |
| **Database** | SQLite (default) / PostgreSQL (with pgvector) |
| **Keyword Search** | SQLite FTS5 (default) / Meilisearch — item + chunk-level indexes |
| **Vector Search** | ChromaDB (SQLite) / pgvector with HNSW (Postgres) — auto-detected |
| **Search Fusion** | Reciprocal Rank Fusion (k=60) + optional cross-encoder reranking |
| **AI** | Ollama / Groq / NVIDIA / Custom (OpenAI/Anthropic-compatible) |
| **Embeddings** | sentence-transformers (local) / NVIDIA (cloud) — auto-dimension detection |
| **Knowledge Graph** | Entity extraction + canonicalization + relation mapping (SQL-based) |
| **Jobs** | Huey (SQLite backend) — stage-based enrichment pipeline |
| **CLI** | argparse, PID management, Docker service orchestration |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS v4 |
| **State** | TanStack Query (server) + Zustand (client) |
| **Editor** | Tiptap (rich text) |
| **Icons** | Lucide React |

---

## Configuration

All config via environment variables with `FDP_` prefix. See [`.env.example`](.env.example).

```bash
# Core
FDP_AI__CHAT_PROVIDER=ollama          # ollama, groq, nvidia, or custom
FDP_SEARCH__BACKEND=sqlite            # sqlite (zero-config) or meilisearch
FDP_AUTH__MODE=single                 # single (no login) or multi (JWT)

# Search & Retrieval
FDP_SEARCH__VECTOR_BACKEND=auto       # auto (pgvector for Postgres, chroma for SQLite), chroma, pgvector
FDP_SEARCH__CHUNK_SIZE_TOKENS=512     # Target chunk size for content splitting
FDP_SEARCH__CHUNK_OVERLAP_TOKENS=64   # Overlap between adjacent chunks

# Reranker (optional, improves search precision)
FDP_RERANK__ENABLED=false             # Enable cross-encoder reranking
FDP_RERANK__MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# Enrichment
FDP_ENRICHMENT__EXTRACT_ENTITIES=false  # Enable entity extraction for concept graph
FDP_ENRICHMENT__SYNTHESIS_ENABLED=true   # LLM-authored entity wiki pages
FDP_ENRICHMENT__SYNTHESIS_THRESHOLD=3    # Regen after N new item mentions
FDP_ENRICHMENT__SYNTHESIS_MIN_INTERVAL_HOURS=24

# Embeddings
FDP_AI__EMBEDDING_PROVIDER=local      # local (sentence-transformers) or nvidia
FDP_AI__EMBEDDING_MODEL=all-MiniLM-L6-v2  # pgvector dimension auto-detected from model
```

Or run `4dpocket setup` for an interactive configuration wizard.

---

## API Reference

Interactive docs at http://localhost:4040/docs when running.

**Items** — `POST /items`, `GET /items`, `GET /items/{id}`, `PATCH /items/{id}`, `DELETE /items/{id}`, `POST /items/bulk`, `POST /items/{id}/archive`, `POST /items/{id}/reprocess`, `GET /items/{id}/related`, `GET /items/{id}/enrichment`, `PATCH /items/{id}/reading-progress`, `POST /items/{id}/download-video`, `GET /items/{id}/media-proxy`

**Notes** — `POST /notes`, `GET /notes`, `GET /notes/{id}`, `PATCH /notes/{id}`, `DELETE /notes/{id}`, `POST /notes/{id}/summarize`, `POST /notes/{id}/generate-title`

**Search** — `GET /search` (full-text), `GET /search/unified` (items + notes), `GET /search/hybrid` (RRF fusion), `GET /search/semantic` (vectors), `GET /search/filters`

**Tags** — Full CRUD, `GET /tags/{id}/items`, `GET /tags/suggestions/merge`, `POST /tags/merge`

**Collections** — Full CRUD, item/note management, `GET /collections/{id}/smart-items`, `GET /collections/{id}/rss`, `PUT /collections/{id}/items/reorder`

**Reading List** — `GET /items/reading-list`, `GET /items/read`, `GET /items/reading-queue`, `GET /items/timeline`

**AI** — `GET /ai/status`, `POST /ai/items/{id}/enrich`, `GET /ai/suggest-collection`, `GET /ai/knowledge-gaps`, `GET /ai/stale-items`, `GET /ai/cross-platform`, `POST /ai/transcribe`

**RSS** — `GET /rss`, `POST /rss`, `PATCH /rss/{id}`, `DELETE /rss/{id}`, `POST /rss/{id}/fetch`, `GET /rss/{id}/entries`, `POST /rss/{id}/entries/{id}/approve`

**Sharing** — `POST /shares`, `GET /shares`, `DELETE /shares/{id}`, `GET /public/{token}`

**Highlights** — Full CRUD, `GET /highlights/search`

**Comments** — `POST /items/{id}/comments`, `GET /items/{id}/comments`, `DELETE /items/{id}/comments/{id}`

**Entities** — `GET /entities`, `GET /entities/{id}`, `GET /entities/{id}/items`, `GET /entities/{id}/related`, `GET /entities/graph`, `POST /entities/{id}/synthesize`

**API Tokens (PATs)** — `POST /auth/tokens`, `GET /auth/tokens`, `DELETE /auth/tokens/{id}`, `POST /auth/tokens/revoke-all`

**MCP** — Streamable-HTTP server at `/mcp`; see [Using 4DPocket as an MCP Server](#using-4dpocket-as-an-mcp-server)

**Admin** — User management, AI config, instance settings, saved filters

**Auth** — Register, login, logout, profile update, password change

**Import/Export** — `POST /import/{source}`, `GET /export/{format}`

---

## Project Structure

```
4dpocket/
├── src/fourdpocket/           # Python backend
│   ├── cli.py                 # CLI entry point (4dpocket command)
│   ├── __main__.py            # python -m fourdpocket support
│   ├── api/                   # 26 FastAPI routers (items, search, entities, AI, ...)
│   ├── models/                # 26 SQLModel tables (items, chunks, entities, relations, ...)
│   ├── processors/            # 17 platform extractors
│   ├── ai/                    # Providers, tagger, summarizer, extractor, canonicalizer, LLM cache
│   ├── search/                # Search service + pluggable backends
│   │   ├── service.py         # SearchService orchestrator (keyword + vector + RRF + rerank)
│   │   ├── base.py            # Protocol definitions (KeywordBackend, VectorBackend, Reranker)
│   │   ├── backends/          # Backend implementations
│   │   │   ├── sqlite_fts_backend.py   # SQLite FTS5 (item + chunk search)
│   │   │   ├── chroma_backend.py       # ChromaDB vector store
│   │   │   ├── pgvector_backend.py     # pgvector with HNSW (auto-dimension)
│   │   │   └── meilisearch_backend.py  # Meilisearch keyword + chunk indexing
│   │   ├── chunking.py        # Content chunking (paragraph/sentence/word split)
│   │   ├── reranker.py        # NullReranker + LocalReranker (cross-encoder)
│   │   └── filters.py         # Inline filter syntax parser
│   ├── sharing/               # Share manager, permissions, feed manager
│   ├── workers/               # Background tasks
│   │   ├── enrichment_pipeline.py  # Stage-based enrichment (chunk→embed→tag→summarize→entities)
│   │   ├── fetcher.py         # URL content extraction
│   │   └── ...                # Media, archiver, RSS, rules, scheduler
│   └── storage/               # User-scoped file storage
├── frontend/                  # React 19 PWA
│   └── src/
│       ├── pages/             # 22 page components
│       ├── components/        # UI components (editor, cards, dialogs, layout)
│       ├── hooks/             # TanStack Query hooks + keyboard shortcuts
│       └── stores/            # Zustand UI state
├── extension/                 # Chrome browser extension
├── tests/                     # 183 pytest tests (incl. PAT + MCP + synthesis)
├── Dockerfile                 # Multi-stage build
├── docker-compose.yml         # Full stack (pgvector/pgvector:pg16 for vector support)
└── .env.example               # Configuration reference
```

---

## Development

See the full [Development Guide](DEVELOPMENT.md) for detailed setup instructions, hybrid configurations, and troubleshooting.

```bash
make dev        # Start dev server (hot reload)
make test       # Run test suite (183 tests)
make lint       # ruff check
make format     # ruff format
make test-cov   # Tests with coverage report
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines, code conventions, and how to add platform processors.

---

## Native Apps (Coming Soon)

- **Android** — Native app with share intent and offline support
- **iOS** — Native app with share extension and widget support

---

## License

GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with &#10084; by <a href="https://onllm.dev">onllm.dev</a>
</p>

<p align="center">
  <a href="https://onllm.dev">onllm.dev</a> &middot; <a href="https://github.com/onllm-dev/4DPocket">GitHub</a> &middot; <a href="https://buymeacoffee.com/prakersh">Support 4DPocket</a>
</p>
