import { Link } from "react-router-dom";
import { RefreshCw, Sparkles } from "lucide-react";
import type { EntitySynthesis } from "@/hooks/use-entities";

const CONFIDENCE_COLORS: Record<string, string> = {
  low: "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300",
  high: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300",
};

interface Props {
  synthesis: EntitySynthesis | null;
  generatedAt: string | null;
  entityMentions: number;
  onRegenerate: () => void;
  regenerating: boolean;
  error?: string | null;
}

function formatRelative(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const mins = Math.floor((now - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function SynthesisPanel({
  synthesis,
  generatedAt,
  entityMentions,
  onRegenerate,
  regenerating,
  error,
}: Props) {
  if (synthesis === null) {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 dark:border-gray-800 p-6 text-center">
        <Sparkles className="h-6 w-6 text-gray-400 dark:text-gray-600 mx-auto mb-2" />
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
          No synthesis yet
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-500 mb-4">
          Synthesis is generated automatically when {Math.max(3 - entityMentions, 0)} more item(s) mention this entity,
          or you can trigger it now.
        </p>
        <button
          onClick={onRegenerate}
          disabled={regenerating || entityMentions < 3}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 text-white text-xs font-medium hover:bg-sky-700 disabled:opacity-50 transition-colors cursor-pointer"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${regenerating ? "animate-spin" : ""}`} />
          Generate now
        </button>
        {error && <p className="mt-2 text-[11px] text-red-600 dark:text-red-400">{error}</p>}
      </div>
    );
  }

  const confidenceStyle =
    CONFIDENCE_COLORS[synthesis.confidence] ?? CONFIDENCE_COLORS.low;

  return (
    <div className="rounded-xl border border-sky-100 dark:border-sky-950/60 bg-gradient-to-br from-sky-50/50 to-white dark:from-sky-950/20 dark:to-gray-900 p-5">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-sky-600 dark:text-sky-400" />
          <h3 className="font-bold text-sm text-gray-900 dark:text-gray-100">Synthesis</h3>
          <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${confidenceStyle}`}>
            {synthesis.confidence} confidence
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-gray-500 dark:text-gray-400">
            {formatRelative(generatedAt)} · from {synthesis.source_item_count} items
          </span>
          <button
            onClick={onRegenerate}
            disabled={regenerating}
            className="p-1 rounded hover:bg-sky-100 dark:hover:bg-sky-900/40 transition-colors cursor-pointer"
            title="Regenerate synthesis"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-sky-600 dark:text-sky-400 ${regenerating ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      <p className="text-sm text-gray-800 dark:text-gray-200 leading-relaxed mb-4">
        {synthesis.summary}
      </p>

      {synthesis.themes.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-1">
            Themes
          </div>
          <div className="flex flex-wrap gap-1.5">
            {synthesis.themes.map((theme) => (
              <span
                key={theme}
                className="inline-block px-2 py-0.5 rounded-full bg-sky-100 dark:bg-sky-950/60 text-[11px] text-sky-700 dark:text-sky-300"
              >
                {theme}
              </span>
            ))}
          </div>
        </div>
      )}

      {synthesis.key_contexts.length > 0 && (
        <div className="mb-4">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Key contexts
          </div>
          <ul className="space-y-2">
            {synthesis.key_contexts.map((c, i) => (
              <li
                key={i}
                className="text-xs text-gray-700 dark:text-gray-300 pl-3 border-l-2 border-sky-200 dark:border-sky-900"
              >
                <span>{c.context}</span>
                {c.source_item_id && (
                  <Link
                    to={`/item/${c.source_item_id}`}
                    className="ml-1 text-sky-600 dark:text-sky-400 hover:underline text-[10px]"
                  >
                    source →
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {synthesis.relationships.length > 0 && (
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-2">
            Relationships
          </div>
          <ul className="space-y-1">
            {synthesis.relationships.map((r, i) => (
              <li key={i} className="text-xs text-gray-700 dark:text-gray-300">
                <span className="font-medium text-gray-900 dark:text-gray-100">{r.entity_name}</span>
                {r.nature && <span className="text-gray-500 dark:text-gray-400"> — {r.nature}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
