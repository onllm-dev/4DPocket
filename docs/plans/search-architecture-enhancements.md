# 4dpocket Search & Retrieval — Architecture Enhancement Plan

**Status:** Draft / brainstorming
**Date:** 2026-04-12
**Owner:** @prakersh
**Scope:** Storage, search, and enrichment layers of 4dpocket

---

## 1. Executive Summary

4dpocket's current search stack (SQLite FTS5 + ChromaDB + RRF hybrid) is functionally solid
for bookmark-grade lookup but plateaus on three axes:

1. **Precision** — items are indexed as single blobs, so paragraph-level matches are lost
   and long articles hit a hard 50 KB content cap (`src/fourdpocket/search/sqlite_fts.py:182`).
2. **Architectural cohesion** — the search facade (`search/indexer.py:29`) branches on
   backend name in every method; `semantic.py` and `hybrid.py` bypass the facade entirely.
3. **Capability** — flat tags and no entity layer mean concept-level queries ("everything
   connected to LangChain") fall back to string matching.

This plan proposes a **six-phase** rework that:

- Introduces **chunks** as the unit of retrieval.
- Adds a **reranker** stage on top of RRF.
- **Finishes the backend abstraction** so `SqliteFtsBackend`, `ChromaBackend`,
  `PgVectorBackend`, `MeilisearchBackend`, and `HybridBackend` all implement one interface.
- Formalizes **ingest as a state machine** with per-stage status, retries, and
  observability.
- Adds **entity extraction + canonicalization** as a new enrichment step.
- Builds a **concept graph** in the primary database (no Neo4j).

The vector-backend strategy is **dual-path**: ChromaDB remains the default for SQLite
deployments; **pgvector** becomes the default for Postgres deployments, enabling
single-query hybrid retrieval via SQL joins.

**Non-goal:** adopting LightRAG as a library or running it as a sidecar. This plan borrows
architectural patterns only.

---

## 2. Current State (as of 2026-04-12)

### 2.1 Stack

| Layer | Current | Files |
|---|---|---|
| Primary DB | SQLite / Postgres (SQLModel, sync) | `models/`, `db.py` |
| Keyword search | SQLite FTS5 (porter, unicode61) with LIKE fuzzy fallback | `search/sqlite_fts.py` |
| Semantic search | ChromaDB PersistentClient, one collection per user | `search/semantic.py` |
| Optional backend | Meilisearch | `search/meilisearch_backend.py` |
| Fusion | Reciprocal Rank Fusion, k=60 | `search/hybrid.py:12` |
| AI enrichment | Tagging (`ai/tagger.py`), summarization (`ai/summarizer.py`) | `ai/` |
| Background jobs | Huey, SQLite backend | `workers/` |

### 2.2 Observed Weaknesses

| Area | Symptom | Root cause |
|---|---|---|
| Chunking | Content capped at 50 KB; one FTS row per item; one vector per item | No chunk layer — item is atomic |
| Search facade | `if backend == 'sqlite' / 'meilisearch'` branches in every `SearchIndexer` method | Facade halfway finished; semantic + hybrid bypass it |
| Ranking | RRF is the only signal; no semantic relevance check | No rerank stage |
| Enrichment | `tagger` / `summarizer` / embeddings called imperatively with no shared state | No pipeline abstraction |
| Tags | Flat strings (`rag`, `RAG`, `retrieval-augmented-generation` are unrelated rows) | No entity/alias layer |
| Relationships | `item_link` exists but no concept-level links across items | No entity-graph |
| Vector store coupling | ChromaDB runs alongside main DB; can't JOIN semantic results with SQL filters | Separate process space |

---

## 3. Goals & Non-Goals

### Goals
- Paragraph-level retrieval quality on articles, PDFs, transcripts.
- Single `SearchBackend` interface, with polymorphic dispatch instead of branching.
- Vector backend parity between SQLite mode (Chroma) and Postgres mode (pgvector).
- Durable, resumable enrichment pipeline with per-stage status.
- Cross-item concept discovery via a lightweight, SQL-native entity graph.
- No new infra dependencies for SQLite users. Postgres users get pgvector as an extension.

### Non-Goals
- Adopting LightRAG (library or sidecar).
- Neo4j or a dedicated graph DB.
- Async/await migration of route handlers (stays sync per `CLAUDE.md`).
- Multi-tenant/team workspaces (deferred — user_id remains the scope today).
- Conversational "chat with your KB" UX (separate roadmap item, built on top of this).

---

## 4. Vector Backend Strategy: ChromaDB or pgvector

The choice follows the primary database, not the user.

| Deployment | Primary DB | Vector backend | Why |
|---|---|---|---|
| Default / personal | SQLite | ChromaDB (current) | Zero new deps, file-based, existing code path |
| Production / multi-user | Postgres | **pgvector** (new) | Unified backup, ACID with item data, joinable with SQL filters |

### 4.1 Why pgvector for Postgres mode

1. **Single-query hybrid** — semantic filter + relational filter in one SQL statement:
   ```sql
   SELECT c.item_id, c.embedding <=> :query AS distance
   FROM item_chunks c
   JOIN knowledge_items i ON i.id = c.item_id
   WHERE i.user_id = :uid
     AND i.is_favorite = true
     AND i.created_at > now() - interval '7 days'
   ORDER BY c.embedding <=> :query
   LIMIT 20;
   ```
   Today this requires two round-trips (Chroma → SQL filter) plus in-memory intersection.

2. **Transactional consistency** — a failed embedding insert rolls back with the item.
   Chroma lives in a separate process and has its own failure modes.

3. **One backup story** — `pg_dump` captures vectors and items atomically.

4. **HNSW indexes** — pgvector's HNSW implementation is production-grade and tunable.

### 4.2 Why ChromaDB stays for SQLite mode

- SQLite has no vector extension story that's as polished as pgvector.
- Chroma's persistent client is already wired up, understood, and tested.
- Shipping sqlite-vss or sqlite-vec adds a loadable-extension install step that
  breaks on Windows and some managed Python environments.
- Keeping Chroma as the SQLite-mode vector store isolates the vector concern.

### 4.3 Unified interface

Both backends implement `VectorBackend`:

```python
class VectorBackend(Protocol):
    def upsert(self, chunks: list[ChunkEmbedding]) -> None: ...
    def query(self, user_id: UUID, embedding: list[float], k: int,
              filters: dict | None = None) -> list[VectorHit]: ...
    def delete(self, ids: list[UUID]) -> None: ...
    def delete_by_item(self, item_id: UUID) -> None: ...
```

Config decides which implementation loads at startup:

```python
# config.py additions
class VectorSettings:
    backend: Literal["chroma", "pgvector"] = "chroma"  # auto-select from DB type
    embedding_dim: int = 1024
    hnsw_m: int = 16          # pgvector only
    hnsw_ef_construction: int = 64  # pgvector only
```

Auto-selection rule: if `DATABASE_URL` starts with `postgresql://`, default
`vector.backend = pgvector`; otherwise `chroma`. User can override.

---

## 5. Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         API layer                           │
│                  (routers in api/, sync)                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                  search.SearchService                       │
│    query planner · filter builder · rerank · roll-up        │
└───────┬───────────────────────┬──────────────────────┬──────┘
        │                       │                      │
┌───────▼────────┐   ┌──────────▼──────────┐   ┌──────▼──────┐
│ KeywordBackend │   │   VectorBackend     │   │  Reranker   │
│  (FTS5/Meili)  │   │ (Chroma/pgvector)   │   │  (optional) │
└───────┬────────┘   └──────────┬──────────┘   └─────────────┘
        │                       │
        └───────────┬───────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                    item_chunks table                        │
│  (id, item_id, user_id, order, text, token_count, hash)     │
└─────────────────────────────────────────────────────────────┘
                    ▲
┌───────────────────┴─────────────────────────────────────────┐
│                EnrichmentPipeline (Huey)                    │
│  chunked → embedded → tagged → summarized → entities        │
│  per-stage status, retries, resumable                       │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│        entities · entity_aliases · entity_relations         │
│           (SQL-native concept graph, user-scoped)           │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Phased Implementation

### Phase 1 — Chunking layer (quality foundation)

**Goal:** retrieval operates on chunks, not item blobs.

#### Schema

```sql
CREATE TABLE item_chunks (
  id              UUID PRIMARY KEY,
  item_id         UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
  user_id         UUID NOT NULL,
  chunk_order     INTEGER NOT NULL,
  text            TEXT NOT NULL,
  token_count     INTEGER NOT NULL,
  char_start      INTEGER NOT NULL,
  char_end        INTEGER NOT NULL,
  content_hash    TEXT NOT NULL,      -- sha1 of text; skip re-embedding if unchanged
  embedding_model TEXT,               -- tracks which model embedded this chunk
  created_at      TIMESTAMPTZ NOT NULL,
  UNIQUE(item_id, chunk_order)
);
CREATE INDEX idx_chunks_item ON item_chunks(item_id);
CREATE INDEX idx_chunks_user ON item_chunks(user_id);
CREATE INDEX idx_chunks_hash ON item_chunks(content_hash);
```

**pgvector mode** adds:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE item_chunks ADD COLUMN embedding vector(1024);
CREATE INDEX idx_chunks_embedding ON item_chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

**Chroma mode** keeps embeddings in Chroma keyed by `chunk_id` (UUID string), not
on the `item_chunks` row.

#### FTS5 virtual table switch

```sql
CREATE VIRTUAL TABLE items_fts USING fts5(
  chunk_id UNINDEXED,
  item_id UNINDEXED,
  user_id UNINDEXED,
  title,         -- only present on chunk 0 (item title)
  url,           -- only present on chunk 0
  text,          -- the chunk body
  tokenize='porter unicode61'
);
```

**Migration path:** maintain `items_fts` (legacy, item-level) alongside the new
`items_fts` table for one release; backfill in a Huey task; flip reads once
backfill completes; drop legacy table.

#### Chunker

```
src/fourdpocket/search/chunking.py
  - chunk_text(text, target_tokens=512, overlap=64) -> list[Chunk]
  - uses tiktoken for token counts
  - splits on paragraph → sentence → hard fallback
  - stores char_start/char_end to enable snippet extraction
```

Chunk size: **512 tokens with 64-token overlap**. Rationale: fits within the
context budget of small embedding models (Nomic, BGE-small) and matches the
sweet spot for most rerankers. Configurable via `FDP_SEARCH__CHUNK_SIZE`.

#### Roll-up for display

Search returns chunk hits. The service layer groups by `item_id`, picks the
best-scoring chunk per item as the snippet, and returns items in the existing
response shape. No API contract change.

#### Config

```python
class SearchSettings:
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    max_chunks_per_item: int = 200   # DoS protection
```

#### Testing

- Unit: chunker handles empty text, text shorter than target, multi-paragraph
  text, text with no whitespace, HTML-stripped content.
- Integration: index a 100-page article, search for a phrase in chunk 47,
  assert the returned snippet is from chunk 47 with correct char offsets.
- Regression: existing FTS5 test suite passes against the new schema.

---

### Phase 2 — Reranker stage

**Goal:** biggest quality lift per line of code.

#### Design

```
src/fourdpocket/search/reranker.py
  class Reranker(Protocol):
      def rerank(self, query: str, docs: list[str], top_k: int) -> list[tuple[int, float]]
  class LocalReranker:    # bge-reranker-base via sentence-transformers
  class CloudReranker:    # Cohere/Voyage — uses existing AI provider pattern
  class NullReranker:     # pass-through (default off)
```

Wire into `hybrid_search`:

1. RRF fuses FTS + semantic to top-50.
2. Fetch chunk texts for the 50.
3. `reranker.rerank(query, texts, top_k=20)`.
4. Return top-20 with rerank score replacing RRF score.

#### Config

```python
class RerankSettings:
    enabled: bool = False
    backend: Literal["local", "cohere", "voyage", "none"] = "none"
    model: str = "BAAI/bge-reranker-base"
    candidate_pool: int = 50   # how many to rerank
    top_k: int = 20            # how many to return
    min_score: float = 0.0     # filter threshold
```

Defaults are **off** so nothing changes for current users until they opt in.

#### Testing

- Unit: rerank order differs from RRF order in a known case.
- Integration: enable local reranker, run a query with a synonym-heavy corpus,
  assert recall@20 improves vs. RRF alone.
- Performance: p50 latency budget +150 ms when reranker is on with candidate
  pool of 50. Fail CI if budget is exceeded.

---

### Phase 3 — Backend abstraction (finish the facade)

**Goal:** one interface, pluggable backends, no more `if backend == ...` branches.

#### Interfaces

```python
# src/fourdpocket/search/base.py

class KeywordBackend(Protocol):
    def init(self) -> None: ...
    def index_chunk(self, chunk: Chunk) -> None: ...
    def delete_by_item(self, item_id: UUID) -> None: ...
    def search(self, query: str, user_id: UUID, filters: Filters,
               limit: int, offset: int) -> list[KeywordHit]: ...

class VectorBackend(Protocol):
    def init(self) -> None: ...
    def upsert(self, chunk_id: UUID, user_id: UUID,
               embedding: list[float], metadata: dict) -> None: ...
    def delete_by_item(self, item_id: UUID) -> None: ...
    def query(self, user_id: UUID, embedding: list[float], k: int,
              filters: Filters | None) -> list[VectorHit]: ...

class HybridBackend:
    def __init__(self, keyword: KeywordBackend, vector: VectorBackend,
                 reranker: Reranker): ...
    def search(self, query: str, ...) -> list[HybridHit]: ...
```

#### Registry

```python
# src/fourdpocket/search/__init__.py

KEYWORD_BACKENDS: dict[str, type[KeywordBackend]] = {
    "sqlite_fts": SqliteFtsBackend,
    "meilisearch": MeilisearchBackend,
}
VECTOR_BACKENDS: dict[str, type[VectorBackend]] = {
    "chroma": ChromaBackend,
    "pgvector": PgVectorBackend,
}

def build_search_service(settings: Settings, db_session_factory) -> SearchService:
    kw = KEYWORD_BACKENDS[settings.search.keyword_backend](db_session_factory)
    vec = VECTOR_BACKENDS[settings.search.vector_backend](db_session_factory)
    rerank = build_reranker(settings.rerank)
    return SearchService(HybridBackend(kw, vec, rerank))
```

#### Migration strategy

1. Introduce new interfaces and `SearchService` alongside the existing
   `SearchIndexer`.
2. Port each backend one at a time: `SqliteFtsBackend` first, then `ChromaBackend`,
   then new `PgVectorBackend`, finally `MeilisearchBackend`.
3. Swap call sites one router at a time (`api/search.py`, `api/items.py`, …).
4. Delete `SearchIndexer` and the legacy hybrid module once all call sites
   are migrated.

#### Testing

- Each backend ships with a shared conformance test suite: "index N chunks,
  query for chunk 47, expect chunk 47 in top 3."
- Run the suite against every backend in CI.

---

### Phase 4 — Enrichment pipeline with status tracking

**Goal:** ingest is a resumable, observable state machine.

#### Schema

```sql
CREATE TABLE enrichment_stages (
  item_id      UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
  stage        TEXT NOT NULL,    -- chunked|embedded|tagged|summarized|entities_extracted
  status       TEXT NOT NULL,    -- pending|running|done|failed|skipped
  attempts     INTEGER NOT NULL DEFAULT 0,
  last_error   TEXT,
  started_at   TIMESTAMPTZ,
  finished_at  TIMESTAMPTZ,
  updated_at   TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (item_id, stage)
);
CREATE INDEX idx_enrichment_status
  ON enrichment_stages(status, stage)
  WHERE status IN ('pending', 'failed');
```

#### Stages

| Stage | Input | Output | Depends on |
|---|---|---|---|
| `chunked` | `KnowledgeItem.content` | `item_chunks` rows | — |
| `embedded` | chunk texts | vectors in `VectorBackend` | `chunked` |
| `tagged` | item title/content | `item_tags` | — |
| `summarized` | item content | `item.summary` | — |
| `entities_extracted` | chunk texts | `entities`, `item_entities`, `entity_relations` | `chunked` |

Stages are independent where possible (tags + summary don't need chunks) to
enable parallelism.

#### Runner

```python
# src/fourdpocket/workers/enrichment.py

@huey.task(retries=3, retry_delay=60)
def run_stage(item_id: UUID, stage: str) -> None:
    with get_session() as db:
        state = get_stage(db, item_id, stage)
        if state.status == 'done':
            return
        mark_running(db, item_id, stage)
        try:
            STAGE_HANDLERS[stage](db, item_id)
            mark_done(db, item_id, stage)
            enqueue_dependents(item_id, stage)
        except Exception as e:
            mark_failed(db, item_id, stage, str(e))
            raise
```

#### Sync fallback

When Huey is not running (`FDP_WORKERS__MODE=sync`), the pipeline runs
in-process right after item creation, using the same stage handlers and the
same status tracking. This preserves the current "works without a worker"
guarantee.

#### Observability

- New endpoint `GET /api/items/{id}/enrichment` returns per-stage status.
- Admin dashboard card: "N items with failed enrichment" with a retry button.
- Structured logs: `stage_started` / `stage_done` / `stage_failed` with
  `item_id`, `stage`, `duration_ms`, `error`.

#### Testing

- Unit: each stage handler is independently testable.
- Integration: kill a running stage mid-flight, assert the item's state is
  `failed`, call retry, assert it completes.
- Regression: existing items without an `enrichment_stages` row are treated
  as "legacy pending" and processed on next touch.

---

### Phase 5 — Entity extraction & canonicalization

**Goal:** turn flat tags into a typed entity layer.

#### Schema

```sql
CREATE TABLE entities (
  id              UUID PRIMARY KEY,
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  canonical_name  TEXT NOT NULL,
  entity_type     TEXT NOT NULL,   -- person|org|concept|tool|product|event|location|other
  description     TEXT,
  item_count      INTEGER NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL,
  UNIQUE(user_id, entity_type, canonical_name)
);
CREATE INDEX idx_entities_user_type ON entities(user_id, entity_type);

CREATE TABLE entity_aliases (
  id          UUID PRIMARY KEY,
  entity_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  alias       TEXT NOT NULL,
  source      TEXT NOT NULL,       -- 'extraction'|'user'|'merge'
  UNIQUE(entity_id, alias)
);
CREATE INDEX idx_aliases_lookup ON entity_aliases(alias);

CREATE TABLE item_entities (
  item_id     UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
  entity_id   UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  chunk_id    UUID REFERENCES item_chunks(id) ON DELETE SET NULL,
  salience    REAL NOT NULL,       -- 0..1, relative importance in item
  context     TEXT,                -- short snippet showing mention
  PRIMARY KEY (item_id, entity_id, chunk_id)
);
CREATE INDEX idx_item_entities_entity ON item_entities(entity_id);
```

**pgvector mode** also adds:

```sql
ALTER TABLE entities ADD COLUMN name_embedding vector(1024);
CREATE INDEX idx_entities_name_embedding ON entities
  USING hnsw (name_embedding vector_cosine_ops);
```

This powers fast canonicalization lookups (see below).

#### Extractor

```
src/fourdpocket/ai/extractor.py
  def extract_entities(chunk_text: str) -> ExtractionResult
```

Prompt modeled on LightRAG's `entity_extraction_system_prompt` with simplified
output:

```json
{
  "entities": [
    {"name": "LangChain", "type": "tool",
     "description": "Python framework for building LLM apps"}
  ],
  "relations": [
    {"source": "LangChain", "target": "RAG", "keywords": "framework, pattern",
     "description": "LangChain provides primitives for building RAG pipelines"}
  ]
}
```

Uses the existing `get_chat_provider().generate_json()` path. Sanitized via
`ai/sanitizer.py` per project rules.

#### Canonicalization

The hard problem. Three-tier cascade:

1. **Exact alias match** — `SELECT entity_id FROM entity_aliases WHERE alias = ?`.
2. **Fuzzy/normalized match** — lowercase, strip punctuation, compare to
   `canonical_name`. Catches `RAG` vs `rag` vs `R.A.G.`.
3. **Embedding similarity** (Postgres + pgvector only) — if entity has
   `name_embedding` within cosine 0.9, treat as same entity.

If no match: create a new entity. If a match: add the extracted name as a new
alias (if different) and increment `item_count`.

For SQLite/Chroma mode, skip tier 3 and rely on tiers 1 + 2. This is acceptable
for personal-scale KBs (< 10k entities).

#### UI surface

- New page `/entities` listing user's entities with counts.
- New filter chip on `/search`: "entities: LangChain" filters by `item_entities`.
- Entity detail page: items mentioning it, related entities.

#### Testing

- Unit: extractor handles empty text, text with no entities, text with 50+
  entities (capped).
- Integration: index the same article twice with different surface forms
  (`LangChain` → `langchain`); assert they canonicalize to one entity with
  two aliases.
- Migration: backfill entities for existing items lazily (on next touch), not
  eagerly.

---

### Phase 6 — Concept graph

**Goal:** cross-item connections without a graph database.

#### Schema

```sql
CREATE TABLE entity_relations (
  id           UUID PRIMARY KEY,
  user_id      UUID NOT NULL,
  source_id    UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  target_id    UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  keywords     TEXT,
  description  TEXT,
  weight       REAL NOT NULL DEFAULT 1.0,   -- accumulates across extractions
  item_count   INTEGER NOT NULL DEFAULT 1,
  created_at   TIMESTAMPTZ NOT NULL,
  updated_at   TIMESTAMPTZ NOT NULL,
  UNIQUE(source_id, target_id)
);
CREATE INDEX idx_relations_source ON entity_relations(source_id);
CREATE INDEX idx_relations_target ON entity_relations(target_id);

CREATE TABLE relation_evidence (
  relation_id  UUID NOT NULL REFERENCES entity_relations(id) ON DELETE CASCADE,
  item_id      UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
  chunk_id     UUID REFERENCES item_chunks(id) ON DELETE SET NULL,
  PRIMARY KEY (relation_id, item_id, chunk_id)
);
```

#### Relations are undirected

`UNIQUE(source_id, target_id)` is enforced with a normalized order (e.g.,
`source_id < target_id` by UUID bytes) to avoid duplicates.

#### Query patterns

```sql
-- Find entities directly related to LangChain
SELECT e.*
FROM entity_relations r
JOIN entities e ON e.id = CASE WHEN r.source_id = :eid THEN r.target_id ELSE r.source_id END
WHERE (r.source_id = :eid OR r.target_id = :eid)
  AND r.user_id = :uid
ORDER BY r.weight DESC
LIMIT 20;

-- 2-hop via recursive CTE
WITH RECURSIVE hops(entity_id, depth) AS (
  SELECT :eid, 0
  UNION
  SELECT CASE WHEN r.source_id = h.entity_id THEN r.target_id ELSE r.source_id END,
         h.depth + 1
  FROM hops h
  JOIN entity_relations r
    ON (r.source_id = h.entity_id OR r.target_id = h.entity_id)
  WHERE h.depth < 2
)
SELECT DISTINCT entity_id FROM hops WHERE depth > 0;
```

Works in both SQLite and Postgres with minor syntax adjustments.

#### UI surface

- Entity detail page gets a "Related concepts" section.
- New `/graph` page: force-directed layout (Cytoscape.js or d3-force) rendering
  a subgraph centered on a selected entity.
- Search results can include a "Related concepts" sidebar alongside item hits.

#### Testing

- Extraction integration: feed 10 articles on overlapping topics, assert the
  relations table is populated with expected edges.
- Query: assert 1-hop and 2-hop queries return correct neighbors with
  user-scoping.

---

## 7. Configuration Changes (cumulative)

```python
# src/fourdpocket/config.py additions

class SearchSettings(BaseModel):
    keyword_backend: Literal["sqlite_fts", "meilisearch"] = "sqlite_fts"
    vector_backend: Literal["chroma", "pgvector"] = "chroma"  # auto from DB
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    max_chunks_per_item: int = 200
    cache_ttl_seconds: int = 300

class VectorSettings(BaseModel):
    embedding_dim: int = 1024
    embedding_model: str = "nomic-embed-text"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 64
    hnsw_ef_search: int = 40

class RerankSettings(BaseModel):
    enabled: bool = False
    backend: Literal["local", "cohere", "voyage", "none"] = "none"
    model: str = "BAAI/bge-reranker-base"
    candidate_pool: int = 50
    top_k: int = 20
    min_score: float = 0.0

class EnrichmentSettings(BaseModel):
    extract_entities: bool = True
    entity_canonicalization_threshold: float = 0.9  # pgvector mode
    max_entities_per_chunk: int = 20
    max_relations_per_chunk: int = 15
```

All reachable via `FDP_SEARCH__*`, `FDP_VECTOR__*`, `FDP_RERANK__*`, `FDP_ENRICHMENT__*`
env vars, per existing convention.

---

## 8. Data Migration Strategy

### 8.1 Alembic migrations

Each phase ships one alembic migration in `migrations/versions/`:

- `20260413_add_item_chunks.py`
- `20260420_add_pgvector_support.py` (Postgres only, no-op on SQLite)
- `20260427_add_enrichment_stages.py`
- `20260504_add_entities_and_relations.py`

### 8.2 Backfill

A dedicated Huey task backfills in the background:

```python
@huey.task()
def backfill_chunks_batch(batch_size: int = 100) -> int:
    with get_session() as db:
        items = db.exec(
            select(KnowledgeItem)
            .outerjoin(ItemChunk, ItemChunk.item_id == KnowledgeItem.id)
            .where(ItemChunk.id == None)
            .limit(batch_size)
        ).all()
        for item in items:
            enqueue_enrichment(item.id)
        return len(items)
```

Backfill runs with low priority, chunks the work, and is resumable via the
enrichment status table. Admin UI surfaces "Backfill progress: X / Y items".

### 8.3 Rollback

Each phase is independently revertible:

- Chunking: drop `item_chunks`, flip FTS5 back to item-level (kept around for
  one release).
- pgvector: drop extension, switch `vector_backend = chroma`.
- Entities: drop tables; item_tags continue to exist.

No phase removes existing user data without an explicit admin action.

---

## 9. Performance Budgets

| Operation | Budget (p50) | Budget (p95) | Notes |
|---|---|---|---|
| Save item (no enrichment) | < 150 ms | < 400 ms | Same as today |
| Enrichment (all stages, async) | < 8 s | < 20 s | Huey background |
| Enrichment (sync fallback) | < 15 s | < 30 s | Only when Huey is off |
| Search (hybrid, no rerank) | < 120 ms | < 300 ms | Same as today |
| Search (hybrid + local rerank) | < 270 ms | < 600 ms | +150 ms rerank budget |
| Entity canonicalization | < 50 ms | < 150 ms | Per entity |

CI fails any PR that regresses these p95 numbers by > 20 %.

---

## 10. Testing Strategy

### 10.1 Unit
- Chunker, reranker, extractor, canonicalizer each have ≥ 90 % line coverage.
- Backend conformance suite runs against every `KeywordBackend` and
  `VectorBackend` implementation.

### 10.2 Integration
- End-to-end: create an item → all stages run → search returns chunk-level
  hits → reranker reorders → entities populated → relations populated.
- Postgres-only suite runs against a real pgvector container in CI.

### 10.3 Property-based
- Chunk char offsets always round-trip: `item.content[chunk.char_start:chunk.char_end] == chunk.text`.
- Entity canonicalization is idempotent: running extraction twice on the
  same chunk produces the same set of entities.

### 10.4 Load
- 10k items, 100k chunks — search p95 holds on both SQLite/Chroma and
  Postgres/pgvector.
- 1k entities, 10k relations — graph 2-hop queries under 100 ms p95.

---

## 11. Risks & Open Questions

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Chunk migration breaks existing FTS queries | Medium | Dual-write period, feature flag, revertible migration |
| pgvector not available in user's managed Postgres | Medium | Auto-fallback to Chroma with a warning; document supported hosts |
| Entity extraction LLM cost for power users | High | Rate limit, batch, configurable off, per-user cap |
| Reranker memory footprint (local model) | Low | Ship as optional extra, not in base install |
| Backfill overwhelms workers | Medium | Low-priority queue, configurable batch size, pause switch |

### Open Questions

1. **Embedding model**: Keep the current default or bump to a better one?
   `nomic-embed-text` (768d) vs `bge-m3` (1024d, multilingual) vs
   `voyage-3-lite` (cloud, 512d). Decision affects the `embedding_dim` column
   type in pgvector mode — changing it later requires a backfill.

2. **Chunk size**: 512 tokens is a reasonable default, but RAG-Anything-style
   workloads (PDFs, transcripts) may benefit from 1024. Make it configurable,
   but what's the default?

3. **Entity types**: Use LightRAG's 11-type taxonomy or a simpler 8-type one
   (`person / org / concept / tool / product / event / location / other`)?
   Fewer types = easier canonicalization + simpler UI, but may lose fidelity.

4. **Rerank cloud providers**: Cohere requires an API key and sends content
   off-box. This conflicts with 4dpocket's self-hosted positioning. Ship only
   a local reranker by default, cloud as explicit opt-in?

5. **Graph visualization**: Cytoscape.js (mature, heavy) vs react-force-graph
   (lighter, less flexible) vs roll our own d3-force component. Blocks Phase 6
   UI but not the data layer.

6. **Relation directionality**: LightRAG treats relations as undirected.
   That's simpler, but some relations (e.g., "X is part of Y") are inherently
   directed. Compromise: store one canonical direction per pair and let the UI
   show it both ways.

---

## 12. Sequencing & Estimates

| Phase | Scope | Est. effort | Prereqs |
|---|---|---|---|
| 1. Chunking | schema, chunker, FTS5 rework, backfill | 3–4 days | — |
| 2. Reranker | interface, local impl, wire into hybrid | 1–2 days | Phase 1 |
| 3. Backend ABC | interfaces, port 4 backends, `SearchService` | 3–4 days | Phase 1 |
| 3a. pgvector | new `PgVectorBackend`, alembic, conformance | 2–3 days | Phase 3 |
| 4. Enrichment SM | schema, runner, sync fallback, observability | 3–4 days | Phase 1 |
| 5. Entities | extractor, canonicalizer, schema, UI | 4–6 days | Phase 1, 4 |
| 6. Concept graph | relations schema, queries, graph UI | 3–5 days | Phase 5 |

**Total:** ~3–4 weeks of focused work, deliverable as 7 PRs.

**Critical path:** Phase 1 unblocks everything else. Phases 2 and 3 can run
in parallel. Phase 4 depends on 1. Phase 5 depends on 1 and 4. Phase 6 depends
on 5.

**Minimum viable slice** (2 PRs): Phase 1 + Phase 2. This alone is the
"dramatic quality improvement" sprint and is worth shipping even if later
phases slip.

---

## 13. Success Metrics

Measured on a dogfood corpus of 1000 saved items:

| Metric | Current baseline | Target after Phase 2 | Target after Phase 6 |
|---|---|---|---|
| Recall @ 20 (hard queries) | ~55 % | ≥ 75 % | ≥ 85 % |
| MRR on "find this specific item" | ~0.42 | ≥ 0.60 | ≥ 0.65 |
| p95 search latency | ~180 ms | ≤ 600 ms (rerank on) | ≤ 600 ms |
| % of items with enrichment failures | unknown | < 2 % | < 2 % |
| Cross-item concept discoverability | 0 (no UI) | 0 | ≥ 40 % unique-concept recall |

"Hard queries" = queries that require synonym handling or concept matching,
curated from real user search logs.

---

## 14. Out of Scope (for this plan)

- Chat / Q&A interface on top of the retrieval layer. That's a separate
  roadmap item that will consume this architecture.
- Multi-modal embeddings (images, audio). Requires different embedding models
  and storage patterns.
- Sharing / team workspaces. `user_id` stays the scope until that lands.
- Sub-chunk citation UI (highlighting exact text in source). Nice-to-have
  after Phase 1 provides `char_start`/`char_end`, but not tracked here.
- Real-time reindex on content edits. Current plan assumes eventual
  consistency via enrichment queue.

---

## 15. Next Steps

1. **Decide the open questions in §11** with @prakersh — especially embedding
   model and chunk size, because they affect the Phase 1 schema.
2. **Prototype Phase 1** on a branch with a real corpus (dogfood the existing
   saved items) to measure the quality delta before committing to the full
   rollout.
3. **Benchmark pgvector vs Chroma** on the same corpus and same queries to
   confirm the dual-backend strategy is worth the maintenance cost.
4. **Turn this plan into 7 issues** in the tracker with phase labels once
   open questions are resolved.
