# 4DPocket MCP Server

4DPocket exposes a Model Context Protocol (MCP) server that lets AI assistants (Claude Desktop, Continue.dev, Cursor, etc.) read and write to your knowledge base using Personal Access Tokens (PATs).

---

## Endpoint

```
POST/GET  http://your-server:4040/mcp/
```

The server is a FastMCP streamable-HTTP app mounted at `/mcp`. Both `/mcp` and `/mcp/` work (a 307 redirect ensures the trailing-slash form is canonical). The `FDP_SERVER__PUBLIC_URL` setting is used as the MCP issuer and resource URL; set it to your public hostname in production.

---

## Minting a PAT

PATs are created via the REST API. You need a valid JWT session (log in via the web UI first, then use the session cookie or JWT to make this call).

```http
POST /api/v1/auth/tokens
Content-Type: application/json
Authorization: Bearer <your-jwt>

{
  "name": "Claude Desktop",
  "role": "editor",
  "all_collections": true,
  "include_uncollected": true,
  "allow_deletion": false,
  "admin_scope": false,
  "expires_at": null
}
```

The response includes `token` — the plaintext PAT in the format `fdp_pat_<6-char-prefix>_<43-char-random>`. This value is shown **exactly once**. Store it securely.

See `src/fourdpocket/api/api_tokens.py:121` for the full request schema.

### PAT Scope Flags

These fields on the token control what the MCP client can do (field names from `src/fourdpocket/models/api_token.py`):

| Field | Type | Default | Description |
|---|---|---|---|
| `role` | `viewer` or `editor` | `viewer` | `editor` tokens can save, update, refresh, delete, and add to collections. `viewer` tokens are read-only. |
| `all_collections` | bool | `true` | Grant access to all of the user's collections, including future ones. |
| `collection_ids` | UUID list | — | Restrict access to specific collections. Used when `all_collections=false`. |
| `include_uncollected` | bool | `true` | Whether the token can see items not in any collection. |
| `allow_deletion` | bool | `false` | Required to call `delete_knowledge`. Set `false` for most clients. |
| `admin_scope` | bool | `false` | Required to call admin REST endpoints. Only mintable by admin users. |
| `expires_at` | datetime or null | `null` | ISO-8601 expiry. `null` means the token never expires (revoke manually if needed). |

---

## Configuring Claude Desktop

Add this to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "4dpocket": {
      "type": "http",
      "url": "http://your-server:4040/mcp/",
      "headers": {
        "Authorization": "Bearer fdp_pat_xxxxxx_yyyyyyy..."
      }
    }
  }
}
```

Restart Claude Desktop. The tools listed below will appear automatically.

## Configuring Continue.dev

In `.continue/config.json`:

```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {
          "type": "http",
          "url": "http://your-server:4040/mcp/"
        },
        "requestOptions": {
          "headers": {
            "Authorization": "Bearer fdp_pat_xxxxxx_yyyyyyy..."
          }
        }
      }
    ]
  }
}
```

---

## Available Tools

These are the 11 tools registered in `src/fourdpocket/mcp/server.py`. The tool names and parameter names are authoritative from that file.

| Tool | Role required | Description |
|---|---|---|
| `search_knowledge` | viewer | Hybrid search (keyword + vector + graph) across the user's knowledge base. Accepts `query`, `limit` (max 50), `item_type`, `tags`, `after`, `before`, `collection_id`. |
| `search_in_collection` | viewer | Search scoped to a single collection. `collection` accepts either the collection UUID or its name (case-insensitive). All other filters behave the same as `search_knowledge`. |
| `get_knowledge` | viewer | Fetch full detail for a single item by `knowledge_id` (UUID): title, content, tags, entities, collections, chunks. |
| `list_collections` | viewer | List collections the PAT has access to. |
| `get_entity` | viewer | Fetch entity detail including LLM-authored synthesis and aliases. `id_or_name` accepts the entity UUID or its canonical name / alias. |
| `get_related_entities` | viewer | Return entities connected to the given one via the concept graph, ranked by relation weight. |
| `save_knowledge` | editor | Persist a new item. Pass either `url` (triggers the fetcher and enrichment pipeline) or `content` (creates a note immediately). Optional: `title`, `tags`, `collection_id`. |
| `update_knowledge` | editor | Edit fields on an existing item by `knowledge_id`. Only fields you pass are changed. `tags`, when provided, fully replace the existing tag set. |
| `refresh_knowledge` | editor | Re-run the enrichment pipeline for an item. Pass `refetch=true` to also re-download URL content. |
| `delete_knowledge` | editor + `allow_deletion` | Hard-delete an item and cascade through chunks, embeddings, entity mentions, and relations. Requires PAT `allow_deletion=true`. |
| `add_to_collection` | editor | Link an existing knowledge item into a collection by `collection_id` and `knowledge_id`. |

---

## Security Notes

- **Token format**: `fdp_pat_<6-char-prefix>_<43-char-random>` — total 56 printable characters. The prefix is stored in plaintext for lookup; only the SHA-256 hash of the full token is stored in `api_tokens.token_hash`. Comparison uses `hmac.compare_digest` to prevent timing attacks.
- **Transport**: Always use HTTPS in production. The extension enforces this for browser clients (`src/fourdpocket/core/api-client.ts:67`), but MCP clients are your responsibility.
- **Least privilege**: Mint separate tokens with narrow scopes. Use `viewer` role unless the client needs to write. Leave `allow_deletion=false` unless explicitly needed.
- **Rotation**: Revoke tokens via `DELETE /api/v1/auth/tokens/{token_id}` or the web UI Admin panel. Use `expires_at` for time-bounded automation tokens.
- **Audit log**: Every MCP tool call is recorded in the `pat_events` table with the tool name and HTTP status code. Review via `GET /api/v1/auth/tokens/{token_id}/events`.
