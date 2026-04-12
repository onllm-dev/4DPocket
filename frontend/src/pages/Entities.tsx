import { useMemo, useState } from "react";
import { Network, Search } from "lucide-react";
import { useEntities, useEntityGraph } from "@/hooks/use-entities";
import { EntityCard } from "@/components/entities/EntityCard";
import { EntityGraphCanvas } from "@/components/entities/EntityGraphCanvas";

type View = "list" | "graph";

const ENTITY_TYPES = [
  "all",
  "person",
  "org",
  "concept",
  "tool",
  "product",
  "event",
  "location",
  "other",
] as const;

export default function Entities() {
  const [view, setView] = useState<View>("list");
  const [type, setType] = useState<(typeof ENTITY_TYPES)[number]>("all");
  const [q, setQ] = useState("");

  const typeFilter = type === "all" ? undefined : type;
  const { data: entities, isLoading } = useEntities({
    entity_type: typeFilter,
    q: q.trim() || undefined,
    limit: 300,
  });
  const graph = useEntityGraph(typeFilter);

  const sorted = useMemo(() => {
    if (!entities) return [];
    return [...entities].sort((a, b) => b.item_count - a.item_count);
  }, [entities]);

  return (
    <div className="animate-fade-in max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Network className="h-6 w-6 text-sky-600" />
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
          Knowledge Graph
        </h1>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden">
          {(["list", "graph"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-4 py-1.5 text-sm font-medium transition-colors cursor-pointer ${
                view === v
                  ? "bg-sky-600 text-white"
                  : "bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
              }`}
            >
              {v === "list" ? "List" : "Graph"}
            </button>
          ))}
        </div>

        <select
          value={type}
          onChange={(e) => setType(e.target.value as typeof type)}
          className="text-sm bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg px-3 py-1.5 text-gray-700 dark:text-gray-300 cursor-pointer"
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t} value={t}>
              {t === "all" ? "All types" : t}
            </option>
          ))}
        </select>

        {view === "list" && (
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-gray-400" />
            <input
              type="text"
              placeholder="Search entities…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg text-gray-700 dark:text-gray-300 focus:ring-2 focus:ring-sky-500 focus:outline-none"
            />
          </div>
        )}
      </div>

      {view === "list" && (
        <>
          {isLoading ? (
            <p className="text-sm text-gray-500">Loading entities…</p>
          ) : sorted.length === 0 ? (
            <div className="rounded-xl border border-dashed border-gray-200 dark:border-gray-800 p-8 text-center">
              <Network className="h-8 w-8 text-gray-400 dark:text-gray-600 mx-auto mb-2" />
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
                No entities yet
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Entities appear after the enrichment pipeline processes your saved items. Make sure
                entity extraction is enabled in Admin → AI.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {sorted.map((e) => (
                <EntityCard key={e.id} entity={e} />
              ))}
            </div>
          )}
        </>
      )}

      {view === "graph" && (
        <>
          {graph.isLoading ? (
            <p className="text-sm text-gray-500">Loading graph…</p>
          ) : graph.data ? (
            <EntityGraphCanvas data={graph.data} />
          ) : (
            <p className="text-sm text-gray-500">Graph unavailable.</p>
          )}
        </>
      )}
    </div>
  );
}
