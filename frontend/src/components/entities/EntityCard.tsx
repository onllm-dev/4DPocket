import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import type { EntitySummary } from "@/hooks/use-entities";

const TYPE_COLORS: Record<string, string> = {
  person: "bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300",
  org: "bg-purple-100 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300",
  concept: "bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300",
  tool: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300",
  product: "bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300",
  event: "bg-fuchsia-100 text-fuchsia-700 dark:bg-fuchsia-950/60 dark:text-fuchsia-300",
  location: "bg-teal-100 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300",
  other: "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
};

export function typeColor(entityType: string): string {
  return TYPE_COLORS[entityType] ?? TYPE_COLORS.other;
}

export function EntityCard({ entity }: { entity: EntitySummary }) {
  return (
    <Link
      to={`/entities/${entity.id}`}
      className="block rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-sm hover:shadow-md transition-all p-4"
    >
      <div className="flex items-start justify-between mb-2 gap-2">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm truncate flex-1">
          {entity.canonical_name}
        </h3>
        {entity.has_synthesis && (
          <Sparkles className="h-3.5 w-3.5 text-sky-500 flex-shrink-0" />
        )}
      </div>
      <div className="flex items-center gap-2 mb-2">
        <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-medium ${typeColor(entity.entity_type)}`}>
          {entity.entity_type}
        </span>
        <span className="text-[11px] text-gray-500 dark:text-gray-400">
          {entity.item_count} mention{entity.item_count === 1 ? "" : "s"}
        </span>
      </div>
      {entity.description && (
        <p className="text-xs text-gray-600 dark:text-gray-400 line-clamp-2">
          {entity.description}
        </p>
      )}
    </Link>
  );
}
