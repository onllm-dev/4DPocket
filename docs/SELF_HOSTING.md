# Self-Hosting 4DPocket

4DPocket is designed to run entirely on your own hardware. This guide covers the quickest path to a running instance with Docker Compose, a full environment-variable reference, and common troubleshooting steps.

---

## Docker Compose Quickstart

**Requirements:** Docker 24+, Docker Compose v2.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/4dpocket.git
cd 4dpocket

# 2. Copy the example environment file and edit it
cp .env.example .env
# At minimum set FDP_AUTH__SECRET_KEY or let the app generate one on first start.

# 3. Start the full stack (backend + worker + optional Meilisearch/ChromaDB)
./app.sh start --sqlite          # Zero-config: SQLite, no Docker services needed
# or
./app.sh start --postgres        # PostgreSQL + Meilisearch (starts Docker services)
# or
./app.sh start --full            # Full stack: adds ChromaDB + Ollama
```

The web UI is available at `http://localhost:5173` (dev) or `http://localhost:4040` (backend / production build). The first registered user automatically becomes admin.

### docker-compose.yml (simple deployment)

```bash
./app.sh docker simple   # Brings up the simplified compose stack
```

This runs the backend container with SQLite at `/data/4dpocket.db` and the Huey worker for background enrichment. Mount `/data` to a persistent volume (see Volume Mounts below).

---

## Volume Mounts

The `/data` directory is critical. It holds:

- `4dpocket.db` — SQLite database (if using SQLite)
- `.secret/secret_key` — JWT signing key (auto-generated on first start if `FDP_AUTH__SECRET_KEY` is unset)
- Media downloads and file attachments

**If `/data` is not a persistent volume, your data and JWT signing key will be lost on container restart.** All JWTs become invalid when the signing key changes.

```yaml
# docker-compose.yml snippet
volumes:
  - ./local-data:/data

# Environment
FDP_STORAGE__BASE_PATH=/data
FDP_DATABASE__URL=sqlite:////data/4dpocket.db
```

---

## Backup and Restore

**SQLite (default)**

Stop the stack, tar the data directory, restart:

```bash
./app.sh stop
tar -czf backup-$(date +%Y%m%d).tar.gz ./local-data
./app.sh start
```

A dedicated `./app.sh db backup` command is planned for a future release. Until then, stopping the stack and archiving the data directory is the safe approach.

**PostgreSQL**

```bash
docker exec 4dpocket-postgres pg_dump -U postgres 4dpocket > backup.sql
```

---

## Environment Variable Reference

All variables use the `FDP_` prefix and nested `__` separators (pydantic-settings convention). See `src/fourdpocket/config.py` for the authoritative list with defaults.

### Database (`FDP_DATABASE__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_DATABASE__URL` | `sqlite:///./data/4dpocket.db` | SQLAlchemy URL. Use `postgresql+psycopg2://user:pass@host/db` for Postgres. |
| `FDP_DATABASE__ECHO` | `false` | Log all SQL statements. Verbose; use only for debugging. |

### Auth (`FDP_AUTH__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_AUTH__SECRET_KEY` | auto-generated | JWT signing key. Set explicitly in production. If unset, the key is persisted to `FDP_STORAGE__BASE_PATH/.secret/secret_key`. |
| `FDP_AUTH__SECRET_KEY_DIR` | — | Override the directory where the auto-generated key is persisted. |
| `FDP_AUTH__TOKEN_EXPIRE_MINUTES` | `10080` (7 days) | JWT lifetime. |
| `FDP_AUTH__MODE` | `single` | `single` (one account, no registration) or `multi` (open registration). |

### Storage (`FDP_STORAGE__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_STORAGE__BASE_PATH` | `./data` | Root directory for the secret key file, media downloads, and file attachments. Mount this as a Docker volume. |
| `FDP_STORAGE__MAX_ARCHIVE_SIZE_MB` | `50` | Maximum size for downloaded media archives. |

### Search (`FDP_SEARCH__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_SEARCH__BACKEND` | `sqlite` | `sqlite` (FTS5) or `meilisearch`. Automatically switched to `meilisearch` when a Postgres database URL is detected. |
| `FDP_SEARCH__MEILI_URL` | `http://localhost:7700` | Meilisearch instance URL. |
| `FDP_SEARCH__MEILI_MASTER_KEY` | — | Meilisearch master key. |
| `FDP_SEARCH__VECTOR_BACKEND` | `auto` | `auto`, `chroma`, or `pgvector`. `auto` picks `pgvector` with Postgres, `chroma` with SQLite. |
| `FDP_SEARCH__CHUNK_SIZE_TOKENS` | `512` | Token size for content chunks indexed for hybrid search. |
| `FDP_SEARCH__CHUNK_OVERLAP_TOKENS` | `64` | Overlap between consecutive chunks. |
| `FDP_SEARCH__MAX_CHUNKS_PER_ITEM` | `200` | Hard cap on chunks per item. |
| `FDP_SEARCH__GRAPH_RANKER_ENABLED` | `true` | Enable entity-graph third RRF input. No-op when the concept graph is empty. |
| `FDP_SEARCH__GRAPH_RANKER_HOP_DECAY` | `0.5` | Contribution of 1-hop neighbors relative to seed entities. |
| `FDP_SEARCH__GRAPH_RANKER_TOP_K` | `50` | Maximum items returned by the graph ranker input. |

### AI (`FDP_AI__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_AI__CHAT_PROVIDER` | `ollama` | `ollama`, `groq`, `nvidia`, or `custom`. |
| `FDP_AI__OLLAMA_URL` | `http://localhost:11434` | Ollama API base URL. |
| `FDP_AI__OLLAMA_MODEL` | `llama3.2` | Model name served by Ollama. |
| `FDP_AI__GROQ_API_KEY` | — | Groq API key. |
| `FDP_AI__NVIDIA_API_KEY` | — | NVIDIA NIM API key. |
| `FDP_AI__CUSTOM_BASE_URL` | — | Base URL for a custom OpenAI-compatible or Anthropic-compatible endpoint. |
| `FDP_AI__CUSTOM_API_KEY` | — | API key for the custom provider. |
| `FDP_AI__CUSTOM_MODEL` | — | Model name for the custom provider. |
| `FDP_AI__CUSTOM_API_TYPE` | `openai` | `openai` or `anthropic`. |
| `FDP_AI__EMBEDDING_PROVIDER` | `local` | `local` (sentence-transformers) or `nvidia`. |
| `FDP_AI__EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model name. |
| `FDP_AI__AUTO_TAG` | `true` | Auto-tag new items via AI. |
| `FDP_AI__AUTO_SUMMARIZE` | `true` | Auto-summarize new items via AI. |
| `FDP_AI__TAG_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence to apply a tag. |
| `FDP_AI__SYNC_ENRICHMENT` | `false` | Run AI enrichment inline (no Huey worker) if set to `true`. |

### Reranker (`FDP_RERANK__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_RERANK__ENABLED` | `false` | Enable cross-encoder reranking of search results. |
| `FDP_RERANK__MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model name. |
| `FDP_RERANK__CANDIDATE_POOL` | `50` | Number of candidates passed to the reranker. |
| `FDP_RERANK__TOP_K` | `20` | Number of results returned after reranking. |

### Enrichment (`FDP_ENRICHMENT__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_ENRICHMENT__EXTRACT_ENTITIES` | `false` | Enable entity + relation extraction. Requires a capable LLM. |
| `FDP_ENRICHMENT__MAX_ENTITIES_PER_CHUNK` | `20` | Entity extraction cap per chunk. |
| `FDP_ENRICHMENT__MAX_RELATIONS_PER_CHUNK` | `15` | Relation extraction cap per chunk. |
| `FDP_ENRICHMENT__MAX_ATTEMPTS` | `5` | Retry limit per enrichment stage before permanent failure. |
| `FDP_ENRICHMENT__SYNTHESIS_ENABLED` | `true` | Enable per-entity LLM synthesis (wiki-style pages). |
| `FDP_ENRICHMENT__SYNTHESIS_MIN_ITEM_COUNT` | `3` | Minimum items mentioning an entity before synthesis runs. |
| `FDP_ENRICHMENT__SYNTHESIS_THRESHOLD` | `3` | Regen synthesis when `item_count - synthesis_item_count >= N`. |
| `FDP_ENRICHMENT__SYNTHESIS_MIN_INTERVAL_HOURS` | `24` | Minimum hours between synthesis regenerations per entity. |
| `FDP_ENRICHMENT__SYNTHESIS_MAX_CONTEXT_ITEMS` | `20` | Maximum evidence items fed to the LLM per synthesis. |

### Server (`FDP_SERVER__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_SERVER__HOST` | `0.0.0.0` | Bind address. |
| `FDP_SERVER__PORT` | `4040` | Bind port. |
| `FDP_SERVER__PUBLIC_URL` | `http://localhost:4040` | Canonical public URL. Used by the MCP server as its issuer/resource URL. Set this to your public domain in production. |
| `FDP_SERVER__CORS_ORIGINS` | `["http://localhost:5173","http://localhost:4040"]` | Allowed CORS origins. Add your frontend URL if it differs. |
| `FDP_SERVER__SECURE_COOKIES` | `false` | Set `true` when serving over HTTPS. |
| `FDP_SERVER__TRUST_PROXY` | `false` | Set `true` when behind a reverse proxy (nginx, Caddy, Traefik). |
| `FDP_SERVER__JSON_LOGS` | `false` | Emit structured JSON log lines (useful for Loki, Datadog, etc.). |

### Email (`FDP_EMAIL__`)

| Variable | Default | Notes |
|---|---|---|
| `FDP_EMAIL__SMTP_HOST` | — | SMTP hostname. Leave empty to disable email (events logged to stdout). |
| `FDP_EMAIL__SMTP_PORT` | `587` | SMTP port. |
| `FDP_EMAIL__SMTP_USER` | — | SMTP username. |
| `FDP_EMAIL__SMTP_PASSWORD` | — | SMTP password. |
| `FDP_EMAIL__SMTP_USE_TLS` | `true` | Use STARTTLS. |
| `FDP_EMAIL__FROM_ADDRESS` | — | Sender email address. |
| `FDP_EMAIL__FROM_NAME` | `4dpocket` | Sender display name. |

---

## Troubleshooting

**Port 4040 already in use**

```bash
./app.sh stop
# Or find and kill the conflicting process:
lsof -i :4040
kill <PID>
```

**Alembic head mismatch (database migration error)**

```bash
./app.sh db migrate   # Runs alembic upgrade head
```

If the schema is severely out of date and migration fails, use `./app.sh db reset` to drop and recreate all tables (this is destructive — back up first).

**Vector backend not detected / "no vector backend"**

- With SQLite: ensure `FDP_SEARCH__VECTOR_BACKEND=auto` or `chroma`. ChromaDB must be installed (`uv sync --all-extras`).
- With PostgreSQL: ensure the `pgvector` extension is enabled (`CREATE EXTENSION IF NOT EXISTS vector;`) and `FDP_SEARCH__VECTOR_BACKEND=auto` or `pgvector`.

**Items stuck in "pending" enrichment**

The Huey worker may not be running. Start it:

```bash
./app.sh start -w   # Worker only
# or
./app.sh status     # Check which services are running
```

If you want inline enrichment without a worker, set `FDP_AI__SYNC_ENRICHMENT=true` (skips embedding; tags and summaries only).
