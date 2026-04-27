# 4DPocket REST API Overview

All routes are prefixed `/api/v1`. Interactive docs (Swagger UI) are available at `/docs`; OpenAPI JSON at `/openapi.json`. This document is a navigation aid — it groups routers and lists endpoints with one-line descriptions. For full request/response schemas, use `/docs`.

Authentication: JWT Bearer token (from `POST /api/v1/auth/login`) or PAT Bearer token (`fdp_pat_*` format from `POST /api/v1/auth/tokens`).

---

## Auth

File: `src/fourdpocket/api/auth.py`

Login, registration, and user-profile management. Accepts both email and username on login.

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register a new user. First registered user becomes admin. |
| POST | `/auth/login` | Log in with username or email + password; returns JWT. |
| GET | `/auth/me` | Return the current authenticated user's profile. |
| POST | `/auth/logout` | Invalidate the current session cookie. |
| PATCH | `/auth/me` | Update the current user's profile fields. |
| DELETE | `/auth/me` | Delete the current user's account. |
| PATCH | `/auth/password` | Change the current user's password. |

---

## API Tokens (PATs)

File: `src/fourdpocket/api/api_tokens.py`

Create and manage Personal Access Tokens for programmatic access and MCP clients. Requires an active JWT session (not a PAT) to mint tokens.

| Method | Path | Description |
|---|---|---|
| POST | `/auth/tokens` | Create a new PAT; returns the plaintext token once. |
| GET | `/auth/tokens` | List all PATs for the current user. |
| DELETE | `/auth/tokens/{token_id}` | Revoke a PAT. |
| GET | `/auth/tokens/{token_id}/events` | Retrieve the audit event log for a PAT. |
| POST | `/auth/tokens/revoke-all` | Revoke all PATs for the current user. |

---

## Items

File: `src/fourdpocket/api/items.py`

Knowledge item CRUD. The core resource. Also includes enrichment controls, media, and bulk operations.

| Method | Path | Description |
|---|---|---|
| POST | `/items` | Create a new knowledge item (URL or note). Triggers enrichment pipeline. |
| GET | `/items` | List items with filtering, sorting, and pagination. |
| GET | `/items/timeline` | Items grouped by date for a timeline view. |
| GET | `/items/reading-queue` | Unread items in reading-queue order. |
| GET | `/items/reading-list` | Items in the reading list. |
| GET | `/items/read` | Items marked as read. |
| GET | `/items/check-url` | Check whether a given URL is already saved. |
| GET | `/items/queue-stats` | Counts for reading queue, favorites, and archived items. |
| GET | `/items/{item_id}` | Fetch a single item by ID. |
| GET | `/items/{item_id}/tags` | List tags attached to an item. |
| PATCH | `/items/{item_id}` | Update item fields (title, description, reading status, etc.). |
| DELETE | `/items/{item_id}` | Delete an item; cascades through chunks, entities, highlights. |
| POST | `/items/{item_id}/tags` | Add a tag to an item. |
| DELETE | `/items/{item_id}/tags/{tag_id}` | Remove a tag from an item. |
| POST | `/items/{item_id}/archive` | Archive an item. |
| POST | `/items/{item_id}/reprocess` | Re-queue an item for enrichment. |
| GET | `/items/{item_id}/related` | Fetch items semantically related to this one. |
| GET | `/items/{item_id}/enrichment` | Fetch enrichment stage statuses for an item. |
| PATCH | `/items/{item_id}/reading-progress` | Update reading progress (scroll position / percentage). |
| POST | `/items/bulk` | Bulk create, update, or delete items. |
| POST | `/items/{item_id}/download-video` | Queue a video download for a URL item. |
| GET | `/items/{item_id}/media-proxy` | Proxy media from the item's source URL. |
| GET | `/items/{item_id}/media/{path}` | Serve downloaded media files stored locally. |

---

## Collections

File: `src/fourdpocket/api/collections.py`

Group items into named collections. Also includes per-collection notes and RSS feed generation.

| Method | Path | Description |
|---|---|---|
| POST | `/collections` | Create a new collection. |
| GET | `/collections` | List all collections for the current user. |
| GET | `/collections/{collection_id}` | Fetch a single collection. |
| PATCH | `/collections/{collection_id}` | Update a collection (name, description, etc.). |
| DELETE | `/collections/{collection_id}` | Delete a collection. |
| POST | `/collections/{collection_id}/items` | Add an item to a collection. |
| DELETE | `/collections/{collection_id}/items/{item_id}` | Remove an item from a collection. |
| PUT | `/collections/{collection_id}/items/reorder` | Reorder items within a collection. |
| GET | `/collections/{collection_id}/smart-items` | AI-curated items suggested for this collection. |
| GET | `/collections/{collection_id}/items` | List items in a collection. |
| GET | `/collections/{collection_id}/rss` | RSS feed for a collection's items. |
| POST | `/collections/{collection_id}/notes` | Add a note to a collection. |
| DELETE | `/collections/{collection_id}/notes/{note_id}` | Remove a note from a collection. |
| GET | `/collections/{collection_id}/notes` | List notes attached to a collection. |

---

## Tags

File: `src/fourdpocket/api/tags.py`

Create, browse, and merge tags across the knowledge base.

| Method | Path | Description |
|---|---|---|
| POST | `/tags` | Create a new tag. |
| GET | `/tags` | List all tags for the current user. |
| GET | `/tags/{tag_id}` | Fetch a single tag. |
| PATCH | `/tags/{tag_id}` | Update a tag's name or metadata. |
| DELETE | `/tags/{tag_id}` | Delete a tag and remove it from all items. |
| GET | `/tags/suggestions/merge` | Get AI-suggested tag merge candidates. |
| POST | `/tags/merge` | Merge two or more tags into one. |
| GET | `/tags/{tag_id}/items` | List items that have this tag. |

---

## Search

File: `src/fourdpocket/api/search.py`

Unified search across items and notes. Supports keyword, vector, hybrid, and filtered search.

| Method | Path | Description |
|---|---|---|
| GET | `/search` | Keyword search across items. |
| GET | `/search/unified` | Unified search returning items and notes together. |
| GET | `/search/hybrid` | Hybrid keyword + vector search with RRF fusion. |
| GET | `/search/semantic` | Pure vector (embedding) semantic search. |
| GET | `/search/filters` | List available filter facets (tags, platforms, types). |

---

## Notes

File: `src/fourdpocket/api/notes.py`

Standalone notes (not attached to a URL item). Supports AI title generation and summarization.

| Method | Path | Description |
|---|---|---|
| POST | `/notes` | Create a new standalone note. |
| GET | `/notes` | List notes for the current user. |
| GET | `/notes/search` | Full-text search within notes. |
| GET | `/notes/{note_id}` | Fetch a single note. |
| PATCH | `/notes/{note_id}` | Update note content or metadata. |
| DELETE | `/notes/{note_id}` | Delete a note. |
| POST | `/notes/{note_id}/tags` | Add a tag to a note. |
| DELETE | `/notes/{note_id}/tags/{tag_id}` | Remove a tag from a note. |
| GET | `/notes/{note_id}/tags` | List tags on a note. |
| POST | `/notes/{note_id}/summarize` | Generate an AI summary for a note. |
| POST | `/notes/{note_id}/generate-title` | Generate an AI title for a note. |

---

## Highlights

File: `src/fourdpocket/api/highlights.py`

Highlighted text passages attached to items (saved from the browser extension or the web UI).

| Method | Path | Description |
|---|---|---|
| GET | `/highlights` | List highlights for the current user. |
| POST | `/highlights` | Create a new highlight. |
| PATCH | `/highlights/{highlight_id}` | Update a highlight's note or color. |
| DELETE | `/highlights/{highlight_id}` | Delete a highlight. |
| GET | `/highlights/search` | Search within highlight text. |

---

## Comments

File: `src/fourdpocket/api/comments.py`

User comments on knowledge items.

| Method | Path | Description |
|---|---|---|
| POST | `/items/{item_id}/comments` | Add a comment to an item. |
| GET | `/items/{item_id}/comments` | List comments on an item. |
| DELETE | `/items/{item_id}/comments/{comment_id}` | Delete a comment. |

---

## Entities

File: `src/fourdpocket/api/entities.py`

Concept graph: entities extracted from knowledge items and their relationships.

| Method | Path | Description |
|---|---|---|
| GET | `/entities/graph` | Full entity graph (nodes + edges) for the current user. |
| GET | `/entities` | List entities, with optional name filter. |
| GET | `/entities/{entity_id}` | Fetch a single entity with synthesis and aliases. |
| POST | `/entities/{entity_id}/synthesize` | Trigger LLM synthesis regeneration for an entity. |
| GET | `/entities/{entity_id}/items` | List items that mention this entity. |
| GET | `/entities/{entity_id}/related` | List entities related to this one via the concept graph. |

---

## Sharing

File: `src/fourdpocket/api/sharing.py`

Share items with other users or via public links.

| Method | Path | Description |
|---|---|---|
| POST | `/shares` | Create a new share (private link, recipient invite, or public link). |
| GET | `/shares` | List shares created by the current user. |
| DELETE | `/shares/{share_id}` | Delete (revoke) a share. |
| POST | `/shares/{share_id}/recipients` | Add a recipient to an existing share. |
| DELETE | `/shares/{share_id}/recipients/{user_id}` | Remove a recipient from a share. |
| GET | `/shares/shared-with-me` | List items shared with the current user by others. |
| POST | `/shares/{share_id}/accept` | Accept a share invitation. |
| GET | `/shares/history` | Browse the sharing history for the current user. |
| GET | `/public/{token}` | Access a publicly shared item by its share token (no auth required). |

---

## Feeds & RSS

### Knowledge Feed (`src/fourdpocket/api/feeds.py`)

Follow other users' public knowledge feeds.

| Method | Path | Description |
|---|---|---|
| POST | `/feeds/subscribe/{user_id}` | Subscribe to another user's public feed. |
| DELETE | `/feeds/unsubscribe/{user_id}` | Unsubscribe from a user's feed. |
| GET | `/feeds` | List items from all subscribed feeds. |

### RSS Subscriptions (`src/fourdpocket/api/rss.py`)

Subscribe to external RSS/Atom feeds; new entries are saved as knowledge items.

| Method | Path | Description |
|---|---|---|
| GET | `/rss` | List RSS subscriptions for the current user. |
| POST | `/rss` | Create a new RSS subscription. |
| PATCH | `/rss/{feed_id}` | Update a subscription (title, poll interval, filters). |
| DELETE | `/rss/{feed_id}` | Remove an RSS subscription. |
| POST | `/rss/{feed_id}/fetch` | Manually trigger a fetch for a subscription. |
| GET | `/rss/{feed_id}/entries` | List feed entries for a subscription. |
| POST | `/rss/{feed_id}/entries/{entry_id}/approve` | Approve a pending feed entry (in `manual` mode). |
| PATCH | `/rss/{feed_id}/entries/{entry_id}` | Update a feed entry's metadata. |

---

## AI

File: `src/fourdpocket/api/ai.py`

On-demand AI operations and AI service status.

| Method | Path | Description |
|---|---|---|
| GET | `/ai/status` | Check the configured AI provider's availability. |
| POST | `/ai/items/{item_id}/enrich` | Manually trigger full AI enrichment for an item. |
| GET | `/ai/suggest-collection` | Get AI suggestions for which collection a URL belongs to. |
| GET | `/ai/knowledge-gaps` | Identify topics underrepresented in the knowledge base. |
| GET | `/ai/stale-items` | Find items whose content has likely gone out of date. |
| GET | `/ai/cross-platform` | Surface content duplicates across platforms. |
| POST | `/ai/transcribe` | Transcribe an uploaded audio/video file. |

---

## Import & Export

File: `src/fourdpocket/api/import_export.py`

Bulk import from external services; export the full knowledge base.

| Method | Path | Description |
|---|---|---|
| POST | `/import/{source}` | Import items from an external source (`pocket`, `bookmarks`, `csv`, `json`). |
| GET | `/export/{format}` | Export all items in the specified format (`json`, `csv`, `html`). |

---

## Settings

File: `src/fourdpocket/api/settings.py`

Per-user preferences (auto-tag, auto-summarize, theme, etc.).

| Method | Path | Description |
|---|---|---|
| GET | `/settings` | Get the current user's settings. |
| PATCH | `/settings` | Update the current user's settings. |

---

## Stats

File: `src/fourdpocket/api/stats.py`

Dashboard statistics for the current user and public user profiles.

| Method | Path | Description |
|---|---|---|
| GET | `/stats` | Dashboard stats: item count, tag count, collection count, recent activity. |
| GET | `/users/{user_id}/public` | Publicly visible statistics for a given user. |

---

## Item Links

File: `src/fourdpocket/api/item_links.py`

Multiple URLs attached to a single "topic node" item.

| Method | Path | Description |
|---|---|---|
| GET | `/items/{item_id}/links` | List all links attached to an item. |
| POST | `/items/{item_id}/links` | Add a link to an item. |
| DELETE | `/items/{item_id}/links/{link_id}` | Remove a link from an item. |
| PUT | `/items/{item_id}/links/reorder` | Reorder links on an item. |

---

## Rules

File: `src/fourdpocket/api/rules.py`

Automation rules that auto-apply tags or collections based on URL patterns, platforms, or content.

| Method | Path | Description |
|---|---|---|
| GET | `/rules` | List automation rules for the current user. |
| POST | `/rules` | Create a new automation rule. |
| PATCH | `/rules/{rule_id}` | Update an automation rule. |
| DELETE | `/rules/{rule_id}` | Delete an automation rule. |

---

## Saved Filters

File: `src/fourdpocket/api/saved_filters.py`

Named smart filters (saved searches) that the user can recall from the UI.

| Method | Path | Description |
|---|---|---|
| GET | `/filters` | List saved filters for the current user. |
| POST | `/filters` | Create a new saved filter. |
| DELETE | `/filters/{filter_id}` | Delete a saved filter. |
| PATCH | `/filters/{filter_id}` | Update a saved filter. |
| GET | `/filters/{filter_id}/execute` | Execute a saved filter and return matching items. |

---

## Admin

File: `src/fourdpocket/api/admin.py`

Instance-level administration. Requires admin role (and JWT session; PATs must have `admin_scope=true`).

| Method | Path | Description |
|---|---|---|
| GET | `/admin/stats` | Instance-wide statistics (user count, item count, storage use). |
| GET | `/admin/users` | List all users on the instance. |
| GET | `/admin/users/{user_id}` | Fetch a specific user. |
| PATCH | `/admin/users/{user_id}` | Update a user (role, active status, quota). |
| DELETE | `/admin/users/{user_id}` | Delete a user and all their data. |
| GET | `/admin/ai-settings` | Get current AI configuration (env defaults + admin panel overrides). |
| PATCH | `/admin/ai-settings` | Update admin-panel AI configuration overrides. |
| GET | `/admin/search-settings` | Get current search configuration. |
| PATCH | `/admin/search-settings` | Update admin-panel search configuration overrides. |
| GET | `/admin/settings` | Get instance settings (MOTD, registration open, etc.). |
| PATCH | `/admin/settings` | Update instance settings. |

---

## Health

File: `src/fourdpocket/api/health.py`

No authentication required.

| Method | Path | Description |
|---|---|---|
| GET | `/health/detailed` | Probe database, search backends, and Huey worker; returns per-subsystem status. |
