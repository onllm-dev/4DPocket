import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { useCurrentUser } from "@/hooks/use-auth";
import {
  useCreateApiToken,
  type CreateTokenResponse,
  type CreateTokenRequest,
} from "@/hooks/use-api-tokens";

const EXPIRY_OPTIONS: { label: string; value: number | null }[] = [
  { label: "Never", value: null },
  { label: "30 days", value: 30 },
  { label: "90 days", value: 90 },
  { label: "1 year", value: 365 },
  { label: "2 years", value: 730 },
];

interface CollectionOption {
  id: string;
  name: string;
}

export function CreateTokenDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (token: CreateTokenResponse) => void;
}) {
  const { data: user } = useCurrentUser();
  const create = useCreateApiToken();

  const { data: collections } = useQuery<CollectionOption[]>({
    queryKey: ["collections", "for-token"],
    queryFn: () => api.get("/api/v1/collections?limit=100"),
  });

  const [name, setName] = useState("");
  const [role, setRole] = useState<"viewer" | "editor">("viewer");
  const [accessMode, setAccessMode] = useState<"all" | "specific">("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [includeUncollected, setIncludeUncollected] = useState(true);
  const [allowDeletion, setAllowDeletion] = useState(false);
  const [adminScope, setAdminScope] = useState(false);
  const [expiryDays, setExpiryDays] = useState<number | null>(null);

  useEffect(() => {
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [onClose]);

  const isAdmin = user?.role === "admin";
  const canSubmit = name.trim().length > 0 &&
    (accessMode === "all" || selected.length > 0) &&
    !create.isPending;

  function toggleSelected(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  function submit() {
    const payload: CreateTokenRequest = {
      name: name.trim(),
      role,
      all_collections: accessMode === "all",
      collection_ids: accessMode === "specific" ? selected : [],
      include_uncollected: includeUncollected,
      allow_deletion: role === "editor" ? allowDeletion : false,
      admin_scope: isAdmin ? adminScope : false,
      expires_in_days: expiryDays,
    };
    create.mutate(payload, {
      onSuccess: (result) => onCreated(result),
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-lg rounded-xl bg-white dark:bg-gray-900 shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-gray-100 dark:border-gray-800">
          <h3 className="text-base font-bold text-gray-900 dark:text-gray-100">
            Generate new token
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer">
            <X className="h-4 w-4 text-gray-500" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="text-xs font-medium text-gray-700 dark:text-gray-300 block mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Claude Desktop"
              className="w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 text-sm text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-sky-500 focus:outline-none"
            />
            <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">Helps you identify this token later.</p>
          </div>

          <div>
            <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">Role</div>
            <div className="flex gap-2">
              {(["viewer", "editor"] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => setRole(r)}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                    role === r
                      ? "bg-sky-600 text-white"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
                  }`}
                >
                  {r === "viewer" ? "Viewer (read-only)" : "Editor (read + write)"}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">Access</div>
            <div className="flex gap-2 mb-2">
              {(["all", "specific"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setAccessMode(m)}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                    accessMode === m
                      ? "bg-sky-600 text-white"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
                  }`}
                >
                  {m === "all" ? "All collections" : "Specific collections"}
                </button>
              ))}
            </div>

            {accessMode === "specific" && (
              <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-2 max-h-40 overflow-y-auto space-y-1">
                {collections && collections.length > 0 ? collections.map((c) => (
                  <label key={c.id} className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selected.includes(c.id)}
                      onChange={() => toggleSelected(c.id)}
                      className="accent-sky-600"
                    />
                    <span className="text-sm text-gray-700 dark:text-gray-300">{c.name}</span>
                  </label>
                )) : (
                  <p className="text-xs text-gray-500 dark:text-gray-400 p-2">No collections yet. Create one first, then issue a scoped token.</p>
                )}
              </div>
            )}

            {accessMode === "specific" && (
              <label className="flex items-center gap-2 mt-2 text-xs text-gray-600 dark:text-gray-400">
                <input
                  type="checkbox"
                  checked={includeUncollected}
                  onChange={(e) => setIncludeUncollected(e.target.checked)}
                  className="accent-sky-600"
                />
                Also include items that aren't in any collection
              </label>
            )}
          </div>

          {role === "editor" && (
            <div className="rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-100 dark:border-red-950 p-3">
              <label className="flex items-center gap-2 text-xs text-red-700 dark:text-red-300">
                <input
                  type="checkbox"
                  checked={allowDeletion}
                  onChange={(e) => setAllowDeletion(e.target.checked)}
                  className="accent-red-600"
                />
                <span className="font-medium">Allow deletion</span>
                <span className="text-red-500/80">— agent can permanently delete knowledge</span>
              </label>
            </div>
          )}

          {isAdmin && (
            <div className="rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-950 p-3">
              <label className="flex items-center gap-2 text-xs text-amber-800 dark:text-amber-300">
                <input
                  type="checkbox"
                  checked={adminScope}
                  onChange={(e) => setAdminScope(e.target.checked)}
                  className="accent-amber-600"
                />
                <span className="font-medium">Include admin scope</span>
                <span className="text-amber-600/80">— agent can manage users + global settings</span>
              </label>
            </div>
          )}

          <div>
            <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">Expiration</div>
            <div className="flex gap-2 flex-wrap">
              {EXPIRY_OPTIONS.map((opt) => (
                <button
                  key={String(opt.value)}
                  onClick={() => setExpiryDays(opt.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                    expiryDays === opt.value
                      ? "bg-sky-600 text-white"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {create.isError && (
            <p className="text-xs text-red-600 dark:text-red-400">
              {create.error?.message ?? "Failed to create token"}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-gray-100 dark:border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={!canSubmit}
            className="px-4 py-2 text-sm font-medium rounded-lg bg-sky-600 text-white hover:bg-sky-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {create.isPending ? "Creating…" : "Generate token"}
          </button>
        </div>
      </div>
    </div>
  );
}
