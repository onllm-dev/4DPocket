# @onllm-dev/4dpocket-mcp

MCP client launcher for [4DPocket](https://github.com/onllm-dev/4DPocket) — connects stdio-based MCP clients (Claude Desktop, Cursor, Claude Code, Zed, etc.) to a remote 4DPocket instance over streamable HTTP with PAT auth.

## Install

No install needed — use via `npx`:

```bash
npx @onllm-dev/4dpocket-mcp --url https://your.pocket.tld --token fdp_pat_xxx
```

## Get a PAT

1. Open your 4DPocket instance → **Settings → API Tokens & MCP**
2. Click **Create Token**, pick a name and scope
3. Copy the `fdp_pat_...` string (shown once)

## Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "4dpocket": {
      "command": "npx",
      "args": [
        "-y",
        "@onllm-dev/4dpocket-mcp",
        "--url", "https://your.pocket.tld",
        "--token", "fdp_pat_xxx"
      ]
    }
  }
}
```

Restart Claude Desktop.

## Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "4dpocket": {
      "command": "npx",
      "args": ["-y", "@onllm-dev/4dpocket-mcp", "--url", "https://your.pocket.tld", "--token", "fdp_pat_xxx"]
    }
  }
}
```

## Claude Code

If your 4DPocket server supports HTTP MCP directly, you can skip this package and wire it natively:

```bash
claude mcp add --transport http 4dpocket https://your.pocket.tld/mcp \
  --header "Authorization: Bearer fdp_pat_xxx"
```

Use `@onllm-dev/4dpocket-mcp` when your client only speaks stdio.

## Env vars

Instead of flags you can use env vars:

```bash
FDP_URL=https://your.pocket.tld FDP_TOKEN=fdp_pat_xxx npx @onllm-dev/4dpocket-mcp
```

## Available tools

Once connected, your MCP client gets these 4DPocket tools:

- `save_knowledge` — save a URL or note
- `search_knowledge` — hybrid search across your saved items
- `get_knowledge` — fetch an item by id
- `update_knowledge` — edit title/notes/tags
- `refresh_knowledge` — re-fetch and reprocess content
- `delete_knowledge` — remove an item (requires `allow_deletion` PAT)
- `list_collections`
- `add_to_collection`
- `get_entity`
- `get_related_entities`

## Troubleshooting

- **`401 Unauthorized`** — the token is wrong, revoked, or doesn't start with `fdp_pat_`. Create a new one.
- **`404 Not Found` on `/mcp`** — your server is older than 0.2.0. Upgrade the 4DPocket instance.
- **`ENOTFOUND` / `ECONNREFUSED`** — the `--url` isn't reachable from your machine. Check VPN / firewall.

## License

MIT
