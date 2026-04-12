import { useState } from "react";
import { KeyRound, Plus, ShieldAlert } from "lucide-react";
import {
  useApiTokens,
  useRevokeApiToken,
  useRevokeAllApiTokens,
  type ApiTokenSummary,
  type CreateTokenResponse,
} from "@/hooks/use-api-tokens";
import { CreateTokenDialog } from "./CreateTokenDialog";
import { ShowTokenOnceDialog } from "./ShowTokenOnceDialog";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function TokenRow({ token, onRevoke }: { token: ApiTokenSummary; onRevoke: (id: string) => void }) {
  const isRevoked = token.revoked_at !== null;
  return (
    <tr className={`${isRevoked ? "opacity-60" : ""} border-t border-gray-100 dark:border-gray-800`}>
      <td className="py-2 px-3">
        <div className="text-sm font-medium text-gray-900 dark:text-gray-100">{token.name}</div>
        <code className="text-[10px] text-gray-500 dark:text-gray-400 font-mono">
          fdp_pat_{token.prefix}_•••
        </code>
      </td>
      <td className="py-2 px-3 text-xs">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full font-medium ${
            token.role === "editor"
              ? "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
              : "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300"
          }`}
        >
          {token.role}
        </span>
        {token.admin_scope && (
          <span className="ml-1 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300">
            admin
          </span>
        )}
        {token.allow_deletion && (
          <span className="ml-1 inline-flex items-center px-2 py-0.5 rounded-full text-[10px] bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300">
            delete
          </span>
        )}
      </td>
      <td className="py-2 px-3 text-xs text-gray-600 dark:text-gray-400">
        {token.all_collections
          ? "All collections"
          : `${token.collection_ids.length} collection${token.collection_ids.length === 1 ? "" : "s"}`}
        {token.include_uncollected && !token.all_collections && (
          <span className="ml-1 text-gray-400">+ uncollected</span>
        )}
      </td>
      <td className="py-2 px-3 text-xs text-gray-600 dark:text-gray-400">
        {formatDate(token.last_used_at)}
      </td>
      <td className="py-2 px-3 text-xs text-gray-600 dark:text-gray-400">
        {formatDate(token.created_at)}
      </td>
      <td className="py-2 px-3 text-xs text-gray-600 dark:text-gray-400">
        {token.expires_at ? formatDate(token.expires_at) : "Never"}
      </td>
      <td className="py-2 px-3 text-right">
        {isRevoked ? (
          <span className="text-[11px] text-gray-400">revoked</span>
        ) : (
          <button
            onClick={() => onRevoke(token.id)}
            className="text-xs text-red-600 dark:text-red-400 hover:underline cursor-pointer"
          >
            Revoke
          </button>
        )}
      </td>
    </tr>
  );
}

export function ApiTokensSection() {
  const { data: tokens, isLoading } = useApiTokens();
  const revoke = useRevokeApiToken();
  const revokeAll = useRevokeAllApiTokens();

  const [creating, setCreating] = useState(false);
  const [newToken, setNewToken] = useState<CreateTokenResponse | null>(null);

  const active = tokens?.filter((t) => t.revoked_at === null) ?? [];

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-sky-600" />
          <h2 className="text-sm font-bold text-gray-900 dark:text-gray-100">
            API Tokens & MCP
          </h2>
        </div>
        <button
          onClick={() => setCreating(true)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 text-white text-xs font-medium hover:bg-sky-700 transition-colors cursor-pointer"
        >
          <Plus className="h-3.5 w-3.5" />
          New token
        </button>
      </div>

      <p className="text-xs text-gray-600 dark:text-gray-400 mb-4">
        Personal access tokens authenticate external agents (Claude Desktop, Cursor, Claude Code, Codex, etc.) against this 4dpocket instance via MCP.
        Each token is scoped to the collections you pick.
      </p>

      {isLoading && (
        <p className="text-xs text-gray-400">Loading tokens…</p>
      )}

      {!isLoading && (tokens?.length ?? 0) === 0 && (
        <p className="text-xs text-gray-500 dark:text-gray-400 py-4">
          No tokens yet. Create one to connect an MCP-capable agent.
        </p>
      )}

      {!isLoading && (tokens?.length ?? 0) > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-500">
                <th className="py-2 px-3 font-medium">Token</th>
                <th className="py-2 px-3 font-medium">Role</th>
                <th className="py-2 px-3 font-medium">Access</th>
                <th className="py-2 px-3 font-medium">Last used</th>
                <th className="py-2 px-3 font-medium">Created</th>
                <th className="py-2 px-3 font-medium">Expires</th>
                <th className="py-2 px-3" />
              </tr>
            </thead>
            <tbody>
              {tokens!.map((t) => (
                <TokenRow key={t.id} token={t} onRevoke={(id) => revoke.mutate(id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {active.length > 1 && (
        <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={() => {
              if (confirm(`Revoke all ${active.length} active tokens? This cannot be undone.`)) {
                revokeAll.mutate();
              }
            }}
            className="inline-flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 hover:underline cursor-pointer"
          >
            <ShieldAlert className="h-3.5 w-3.5" />
            Revoke all active tokens
          </button>
        </div>
      )}

      {creating && (
        <CreateTokenDialog
          onClose={() => setCreating(false)}
          onCreated={(result) => {
            setCreating(false);
            setNewToken(result);
          }}
        />
      )}

      {newToken && (
        <ShowTokenOnceDialog
          token={newToken}
          onClose={() => setNewToken(null)}
        />
      )}
    </div>
  );
}
