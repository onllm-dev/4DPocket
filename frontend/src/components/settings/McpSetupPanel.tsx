import { useState } from "react";
import { Check, Copy } from "lucide-react";

type ClientKey = "claude-desktop" | "cursor" | "raw";

function getMcpUrl(): string {
  if (typeof window === "undefined") return "http://localhost:4040/mcp";
  return `${window.location.origin}/mcp`;
}

function mcpConfig(client: ClientKey, token: string | null): string {
  const url = getMcpUrl();
  const tokenValue = token ?? "YOUR_TOKEN_HERE";
  switch (client) {
    case "claude-desktop":
    case "cursor":
      return JSON.stringify(
        {
          mcpServers: {
            "4dpocket": {
              url,
              headers: { Authorization: `Bearer ${tokenValue}` },
            },
          },
        },
        null,
        2,
      );
    case "raw":
      return JSON.stringify(
        {
          name: "4dpocket",
          url,
          headers: { Authorization: `Bearer ${tokenValue}` },
        },
        null,
        2,
      );
  }
}

const CLIENT_LABELS: { key: ClientKey; label: string }[] = [
  { key: "claude-desktop", label: "Claude Desktop" },
  { key: "cursor", label: "Cursor" },
  { key: "raw", label: "Raw JSON" },
];

const PATH_HINTS: Record<ClientKey, string> = {
  "claude-desktop": "Add to ~/Library/Application Support/Claude/claude_desktop_config.json (macOS) or %APPDATA%\\Claude\\claude_desktop_config.json (Windows).",
  "cursor": "Add to ~/.cursor/mcp.json or through Cursor → Settings → MCP.",
  "raw": "Generic streamable-HTTP MCP server entry. Adapt to any MCP-compatible client.",
};

export function McpSetupPanel({ token }: { token: string | null }) {
  const [active, setActive] = useState<ClientKey>("claude-desktop");
  const [copied, setCopied] = useState(false);

  const config = mcpConfig(active, token);

  async function copy() {
    try {
      await navigator.clipboard.writeText(config);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
        Connect an MCP client
      </div>
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-800 mb-2">
        {CLIENT_LABELS.map((c) => (
          <button
            key={c.key}
            onClick={() => setActive(c.key)}
            className={`px-3 py-1.5 text-xs font-medium border-b-2 transition-colors cursor-pointer ${
              active === c.key
                ? "border-sky-600 text-sky-600 dark:text-sky-400"
                : "border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            }`}
          >
            {c.label}
          </button>
        ))}
      </div>

      <p className="text-[11px] text-gray-500 dark:text-gray-400 mb-2">
        {PATH_HINTS[active]}
      </p>

      <div className="relative">
        <pre className="rounded-lg bg-gray-900 dark:bg-black text-gray-100 text-xs p-3 overflow-x-auto font-mono">
{config}
        </pre>
        <button
          onClick={copy}
          className={`absolute top-2 right-2 px-2 py-1 rounded text-[10px] font-medium cursor-pointer transition-colors ${
            copied ? "bg-green-600 text-white" : "bg-gray-700 text-gray-100 hover:bg-gray-600"
          }`}
        >
          {copied ? <><Check className="inline h-3 w-3 mr-0.5" /> Copied</> : <><Copy className="inline h-3 w-3 mr-0.5" /> Copy</>}
        </button>
      </div>

      {!token && (
        <p className="text-[11px] text-amber-600 dark:text-amber-400 mt-2">
          Replace <code>YOUR_TOKEN_HERE</code> with the token plaintext from the dialog above.
        </p>
      )}
    </div>
  );
}
