# PAT + MCP + Entity Synthesis — Implementation Plan

**Status:** ✅ Complete (automated verification)
**Started:** 2026-04-12
**Completed:** 2026-04-12
**Owner:** @prakersh
**Target version:** 0.2.0

---

## 1. Executive Summary

Add end-to-end integration so external LLM agents (Claude Desktop, Cursor, Claude Code, Codex, etc.) can treat a 4dpocket instance as persistent memory via the Model Context Protocol.

Four intertwined deliverables:

1. **Personal Access Tokens (PATs)** — per-user API tokens with collection-scoped ACL, role (viewer/editor), optional admin scope, optional deletion permission. First non-JWT authentication path in the codebase.
2. **MCP server** — FastMCP streamable-HTTP, mounted at `/mcp`, 10 tools covering the persist-recall-navigate-update-delete loop.
3. **Entity synthesis** — LLM-authored structured-JSON wiki pages per entity, regenerated when mentions accrue. Realises the Karpathy LLM-wiki pattern on top of the existing entity graph.
4. **UI surfaces** — API Tokens + MCP section inside `/settings`; new comprehensive Entity browser (list + detail + force-directed graph) consistent with existing Tailwind + Doraemon-blue design system.

---

## 2. Decision Log

All decisions locked via user Q&A before implementation.

| # | Decision | Value |
|---|---|---|
| D1 | MCP transport | Streamable HTTP, mounted at `/mcp` on existing FastAPI app, stateless, JSON responses |
| D2 | Token format | `fdp_pat_<6char-id>_<43char-secret>`; sha256(full) stored; `hmac.compare_digest` verification; 6-char id is unique DB lookup key |
| D3 | Auth precedence | `Authorization: Bearer fdp_pat_...` routes to PAT resolver; else JWT; both land in `get_current_user` |
| D4 | ACL model | role ∈ {viewer, editor}; `all_collections` bool; `collection_ids` list when false; `include_uncollected` bool; `allow_deletion` bool (explicit opt-in); `admin_scope` bool (admin users only) |
| D5 | Profile UI | Inline in existing `/settings`; add "API Tokens & MCP" section. Do NOT create `/profile` route. |
| D6 | Synthesis trigger | Automatic: when `item_count - synthesis_item_count >= threshold` AND `min_interval_hours` has passed AND `item_count >= min_item_count`. Plus manual regen endpoint. |
| D7 | DB migrations | Use existing `SQLModel.metadata.create_all` + `db/session.py:_ensure_columns` auto-migration. No alembic version files. |
| D8 | MCP tool naming | No prefix (MCP clients namespace per-server). `search_knowledge`, `get_knowledge`, etc. |
| D9 | Uncollected items | Per-token toggle `include_uncollected` |
| D10 | Admin + PAT | Admin scope opt-in at creation; checkbox only visible to admins |
| D11 | MCP surface | 10 essential tools (persist-recall-navigate CRUD + refresh) — NOT a rich catalog |
| D12 | Write scope model | Single editor bit (not per-capability scopes) |
| D13 | Delete safety | PAT `allow_deletion` flag only (no extra tool-call confirm arg) |
| D14 | Password change → PATs | PATs remain independent; "Revoke all tokens" button as big red button |
| D15 | Token expiry default | No expiry (user can set 30d/90d/1y optionally) |
| D16 | Synthesis cadence | Balanced: `min_item_count=3`, `threshold=3`, `min_interval_hours=24` |
| D17 | Synthesis format | Structured JSON `{summary, themes[], key_contexts[], relationships[], confidence, last_updated, source_item_count}` |
| D18 | Entity UI | Full: list + detail + interactive force-directed graph |
| D19 | Graph library | React Flow |
| D20 | Graph sidebar | Single "Knowledge Graph" entry, tabs for List/Graph inside |
| D21 | MCP config snippets | Tabs: Claude Desktop + Cursor + Raw JSON |
| D22 | Version bump | 0.1.6 → 0.2.0 |

---

## 3. MCP Tool Surface

10 tools. Role column = minimum PAT role. Flags = additional PAT flags required.

| Tool | Role | Flags | Purpose |
|---|---|---|---|
| `save_knowledge(url?, content?, title?, tags?, collection_id?)` | editor | — | Persist: URL triggers fetcher; content creates a note |
| `search_knowledge(query, limit, item_type?, tags?, after?, before?, collection_id?)` | viewer | — | Chunk-level hybrid retrieval |
| `get_knowledge(id)` | viewer | — | Full detail: content, summary, tags, entities, linked_items, highlights, collections, enrichment status |
| `update_knowledge(id, title?, content?, tags?, description?, is_favorite?, is_archived?)` | editor | — | Edit existing item |
| `refresh_knowledge(id, refetch=False)` | editor | — | Re-run enrichment; `refetch=true` also re-downloads URL content |
| `delete_knowledge(id)` | editor | `allow_deletion=true` | Hard delete (cascades through all related models) |
| `list_collections()` | viewer | — | Enumerate accessible collections |
| `add_to_collection(collection_id, knowledge_id)` | editor | — | Organize persisted items |
| `get_entity(id_or_name)` | viewer | — | Entity detail with synthesis + aliases |
| `get_related_entities(entity_id_or_name, limit=10)` | viewer | — | 1-hop associative trail from concept graph |

---

## 4. Phase 1 — PAT Backend

### 4.1 New files
- [x] `src/fourdpocket/models/api_token.py` — `ApiToken`, `ApiTokenCollection`
- [x] `src/fourdpocket/api/api_token_utils.py` — generate, hash, verify, ACL helpers
- [x] `src/fourdpocket/api/api_tokens.py` — CRUD endpoints at `/api/v1/auth/tokens`

### 4.2 Modified files
- [x] `src/fourdpocket/models/base.py` — add `ApiTokenRole` enum
- [x] `src/fourdpocket/models/__init__.py` — register new models
- [x] `src/fourdpocket/api/deps.py` — handle `fdp_pat_*` in token resolution; add `get_current_user_pat_aware`, `require_role`, `require_delete_permission`, `require_admin_scope`
- [x] `src/fourdpocket/api/router.py` — register api_tokens router
- [x] `src/fourdpocket/search/base.py` — add `collection_id`, `allowed_item_ids` to `SearchFilters`
- [x] `src/fourdpocket/search/service.py` — apply collection filter (post-retrieval intersect)

### 4.3 API endpoints
- [x] `POST /api/v1/auth/tokens` — create; returns plaintext ONCE
- [x] `GET /api/v1/auth/tokens` — list user's active + revoked tokens (metadata only)
- [x] `DELETE /api/v1/auth/tokens/{id}` — soft-revoke (set `revoked_at`)
- [x] `POST /api/v1/auth/tokens/revoke-all` — revoke all user's tokens (big red button)

### 4.4 Security requirements
- [x] Token plaintext shown in response exactly once, never logged
- [x] Prefix indexed for O(1) lookup
- [x] `hmac.compare_digest` on hash comparison
- [x] Dummy-compare when prefix not found (avoid timing leak)
- [x] Admin endpoints reject PATs without `admin_scope=true`
- [x] `delete_knowledge` rejects PATs without `allow_deletion=true` (helper in place; enforced in Phase 2 tools)
- [x] Write tools reject `viewer` role (helper in place; enforced in Phase 2 tools)
- [x] Disabled user's PATs stop working (check `User.is_active`)
- [x] Expired PATs rejected
- [x] `last_used_at` updated (debounced to once/minute max)

### 4.5 Tests
- [x] `tests/test_api/test_api_tokens.py` — create, list, revoke, revoke-all, expiry, show-once
- [x] `tests/test_api/test_pat_auth.py` — PAT authenticates existing endpoints, admin endpoints reject non-admin-scope PATs, revoked token rejection, disabled user rejection
- [x] `tests/test_search/test_collection_filter.py` — search respects `allowed_item_ids` + `collection_id`

### 4.6 Checkpoint C1 ✅
- [x] Full test suite green: 151/151 (128 existing + 23 new)
- [x] `ruff check` clean on all Phase 1 files
- [x] PAT resolves on every existing endpoint via the unified `get_current_user` path
- [x] Admin guard rejects non-admin-scope PATs even when owner is admin

---

## 5. Phase 2 — MCP Server

### 5.1 Dependency
- [x] Add `mcp>=1.12` to `pyproject.toml` (installed 1.27.0)

### 5.2 New files
- [x] `src/fourdpocket/mcp/__init__.py`
- [x] `src/fourdpocket/mcp/server.py` — FastMCP instance, tool registration
- [x] `src/fourdpocket/mcp/auth.py` — `PATTokenVerifier` implementing MCP `TokenVerifier`
- [x] `src/fourdpocket/mcp/tools.py` — all 10 tool implementations as pure functions
- [x] `src/fourdpocket/mcp/serializers.py` — `knowledge_detail`, `entity_with_synthesis`, `related_entity` serializers

### 5.3 Modified files
- [x] `src/fourdpocket/main.py` — mount `mcp_app` at `/mcp`; lifespan guards against double-`run()` under pytest

### 5.4 Tool implementations
- [x] `save_knowledge`
- [x] `search_knowledge`
- [x] `get_knowledge`
- [x] `update_knowledge`
- [x] `refresh_knowledge`
- [x] `delete_knowledge` (gated by `allow_deletion`)
- [x] `list_collections`
- [x] `add_to_collection`
- [x] `get_entity`
- [x] `get_related_entities`

### 5.5 Tests
- [x] `tests/test_mcp/__init__.py`
- [x] `tests/test_mcp/test_mcp_auth.py` — token verifier accepts valid, rejects invalid/revoked/expired; scopes reflect flags
- [x] `tests/test_mcp/test_mcp_tools.py` — each tool: role enforcement, ACL enforcement, happy path (14 cases)

### 5.6 Checkpoint C2 ✅
- [x] App boots with `/mcp` mounted (routes: 147)
- [x] Token verifier resolves PATs, returns scopes that reflect flags
- [x] Viewer PAT rejected from write tools; editor allowed
- [x] `delete_knowledge` rejects when `allow_deletion=false`; succeeds when set
- [x] Collection-scoped token returns only allowed items from `search_knowledge`
- [x] Full suite: 170/170 green (128 original + 42 new PAT+MCP tests)

---

## 6. Phase 3 — Entity Synthesis

### 6.1 Model additions
- [x] `src/fourdpocket/models/entity.py` — add `synthesis` (JSON column), `synthesis_generated_at` (nullable timestamptz), `synthesis_item_count` (default 0), `synthesis_confidence` (str, nullable)

### 6.2 Config additions
- [x] `src/fourdpocket/config.py` (`EnrichmentSettings`):
  - `synthesis_enabled: bool = True`
  - `synthesis_min_item_count: int = 3`
  - `synthesis_threshold: int = 3`
  - `synthesis_min_interval_hours: int = 24`
  - `synthesis_max_context_items: int = 20`

### 6.3 New files
- [x] `src/fourdpocket/ai/synthesizer.py` — `synthesize_entity(entity_id, db) -> dict` returning structured JSON; `should_regenerate(entity) -> bool` for pipeline guard

### 6.4 Synthesis JSON schema
```json
{
  "summary": "2-4 sentence neutral description, grounded in sources",
  "themes": ["short recurring-context phrases"],
  "key_contexts": [
    {"context": "1-2 sentence snippet from a key item", "source_item_id": "uuid"}
  ],
  "relationships": [
    {"entity_name": "X", "nature": "brief description of relationship"}
  ],
  "confidence": "low|medium|high",
  "last_updated": "iso8601",
  "source_item_count": 7
}
```

### 6.5 Pipeline integration
- [x] `src/fourdpocket/workers/enrichment_pipeline.py`:
  - Added `synthesized` to `STAGES`
  - Set `STAGE_DEPS["synthesized"] = ["entities_extracted"]`
  - New `handle_synthesis(db, item_id, user_id)`: iterates entities touched by this item, applies `should_regenerate` guard, calls `synthesize_entity` inline (runs under Huey when enabled, sync fallback otherwise)

### 6.6 API
- [x] `src/fourdpocket/api/entities.py`:
  - Surfaces `synthesis`, `synthesis_generated_at`, `synthesis_confidence`, `synthesis_item_count` in `/entities/{id}`
  - `has_synthesis` + `synthesis_confidence` in list view
  - `POST /api/v1/entities/{id}/synthesize?force=bool` — force regeneration with cooldown + min-count guards
  - New `GET /entities/graph` — returns nodes + edges for frontend graph view

### 6.7 Tests
- [x] `tests/test_ai/test_synthesizer.py` — 12 tests:
  - Valid payload round-trip; confidence/item_count persisted
  - Below min_item_count: no synthesis
  - No evidence: no synthesis
  - NoOp provider: graceful `None`
  - Invalid JSON (missing summary) rejected
  - `should_regenerate` matrix: first-time, below-min, threshold, interval
  - Force-regenerate endpoint + 429 cooldown + `?force=true` bypass

### 6.8 Checkpoint C3 ✅
- [x] Saving an item that mentions an entity crossing 3 mentions auto-generates `entity.synthesis`
- [x] JSON schema round-trips through API
- [x] NoOp provider does not crash
- [x] Full suite: 182/182 green (170 + 12 new synthesizer tests)

---

## 7. Phase 4 — Frontend

### 7.1 Dependencies
- [x] Add `reactflow@^11.11` to `frontend/package.json`

### 7.2 Hooks
- [x] `frontend/src/hooks/use-api-tokens.ts` — list/create/revoke/revoke-all mutations
- [x] `frontend/src/hooks/use-entities.ts` — list, detail, graph (entities + relations), synthesis regeneration

### 7.3 Settings — API Tokens section
- [x] `frontend/src/components/settings/ApiTokensSection.tsx` — top-level wrapper with tokens table + revoke-all
- [x] `frontend/src/components/settings/CreateTokenDialog.tsx` — full form (name, role, expiry, access mode, include_uncollected, allow_deletion, admin_scope admins-only)
- [x] `frontend/src/components/settings/ShowTokenOnceDialog.tsx` — copy-once display with embedded MCP setup
- [x] `frontend/src/components/settings/McpSetupPanel.tsx` — tabbed config (Claude Desktop / Cursor / Raw JSON)
- [x] `frontend/src/pages/Settings.tsx` — mounts `ApiTokensSection` + reference `McpSetupPanel`

### 7.4 Entity UI
- [x] `frontend/src/pages/Entities.tsx` — tabs (List | Graph), filter by type, search, sort by item_count
- [x] `frontend/src/pages/EntityDetail.tsx` — synthesis panel + linked items + related entities radial mini-graph
- [x] `frontend/src/components/entities/EntityCard.tsx`
- [x] `frontend/src/components/entities/SynthesisPanel.tsx` — structured JSON rendered with themed sections
- [x] `frontend/src/components/entities/EntityGraphCanvas.tsx` — React Flow wrapper, type-colored nodes, edge-weighted edges, click-to-navigate
- [x] `frontend/src/components/entities/RelatedEntitiesMiniGraph.tsx` — radial SVG layout

### 7.5 Navigation
- [x] `frontend/src/App.tsx` — `/entities`, `/entities/:id` routes
- [x] `frontend/src/components/layout/Sidebar.tsx` — "Knowledge Graph" sidebar entry under Discover (lucide `Network`)

### 7.6 Design compliance
- [x] Doraemon blue `#0096C7` primary
- [x] Rounded-xl cards, existing border/shadow pattern
- [x] Dark mode parity
- [x] Matches typography + spacing scale

### 7.7 Build
- [x] `pnpm build` green (tsc + vite)
- [x] Bundle additions: Entities page lazy-loaded (~147KB gz 48KB), EntityDetail (~11KB), React Flow core (~42KB)

---

## 8. Phase 5 — Tests (consolidated)

### 8.1 Test files
- [ ] `tests/test_api/test_api_tokens.py`
- [ ] `tests/test_api/test_pat_auth.py`
- [ ] `tests/test_search/test_collection_filter.py`
- [ ] `tests/test_mcp/test_mcp_auth.py`
- [ ] `tests/test_mcp/test_mcp_tools.py`
- [ ] `tests/test_ai/test_synthesizer.py`

### 8.2 Success criteria
- [ ] `uv run pytest tests/ -x -q` passes
- [ ] `make lint` / `ruff check` passes
- [ ] No new warnings from existing tests

---

## 9. Phase 6 — Docs & Release

- [x] Update `README.md`: "Using 4DPocket as an MCP Server" section with PAT creation, Claude Desktop / Cursor / Raw JSON snippets, tool list, synthesis overview
- [x] Update `CLAUDE.md`: PAT + MCP added to stack list; dedicated "PATs + MCP" section with token format, ACL flags, resolver, admin guard, tool list, synthesis config
- [x] Bump versions to **0.2.0**:
  - [x] `pyproject.toml`
  - [x] `frontend/package.json`
  - [x] `extension/package.json` — N/A (no file in repo)
- [x] Final `uv run pytest tests/ -q` — **182 passed** (60s)
- [x] Final `uv run ruff check src/ tests/` — **All checks passed**
- [x] `pnpm build` — clean tsc + vite build

---

## 10. Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| PAT plaintext in logs | Medium | Code review all logger calls; token comparisons use `compare_digest`; only prefix logged |
| Timing attack on token lookup | Low | Prefix index O(1); always run `compare_digest` even on miss (dummy) |
| MCP client rejects server without OAuth discovery | Low | Confirm during C2; add minimal `/.well-known` if needed |
| Collection filter breaks search performance | Low | Post-retrieval intersect adds O(n) over top-k; acceptable |
| Entity synthesis cost on bulk imports | Low | `min_interval_hours=24` caps per-entity regen; LLM cache absorbs dups |
| React Flow bundle size | Low | ~200KB; lazy-loaded via existing `lazy()` pattern |
| `_ensure_columns` doesn't create new tables | Confirmed OK | `SQLModel.metadata.create_all(engine)` in `init_db()` handles new tables |
| Single-user mode + PAT interaction | Low | PATs always tied to specific user_id; single-user mode auto-user resolution unaffected |

---

## 11. Progress Log

### 2026-04-12
- Plan written and decisions locked
- Phase 1 complete: PAT backend shipped, 23 new tests, 151/151 full suite green
- Phase 2 complete: 5 new MCP files, 10 tools, mounted at /mcp, 19 new tests
- Phase 3 complete: Entity synthesis (model + synthesizer + pipeline + API + graph endpoint), 12 new tests
- Phase 4 complete: Frontend UI shipped (13 new files, 2 modified), build clean
- Phase 5-6 complete: Docs + version bump to 0.2.0; final verification passed

### Final totals
- **Backend:** 13 new Python files, 8 modified
- **Frontend:** 13 new TSX files, 3 modified (Sidebar, App, Settings)
- **Tests:** 54 new tests (42 PAT+MCP + 12 synthesizer), 182 total, full suite green
- **Dependencies added:** `mcp>=1.12` (Python), `reactflow@^11.11` (frontend)
- **Version:** 0.1.6 → 0.2.0

(Updated as work progresses.)

---

## 12. Verification Checklist (final release gate)

Before merging:
- [x] All Phase 1 checkboxes ticked
- [x] All Phase 2 checkboxes ticked
- [x] All Phase 3 checkboxes ticked
- [x] All Phase 4 checkboxes ticked
- [x] All Phase 5 checkboxes ticked
- [x] All Phase 6 checkboxes ticked
- [ ] **Manual MCP integration test** (requires running instance): Claude Desktop connects to `http://<host>:4040/mcp` with Bearer PAT and successfully calls `search_knowledge` and `save_knowledge`
- [ ] **Manual UI walkthrough** (requires running instance): token create/copy/revoke in `/settings`; entity list/detail/graph at `/entities`
- [x] No lingering TODOs or unused imports in changed code
- [x] Every new function has a docstring where behavior isn't obvious
- [x] Version bumped

Manual verification items remaining are user-run smoke tests once the branch is pulled locally. All automated verification is green.
