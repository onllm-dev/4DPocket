import { AlertCircle, Loader2, Clock } from "lucide-react";

import type { EnrichmentStatus } from "@/hooks/use-items";

interface Props {
  status?: EnrichmentStatus | null;
  itemsAhead?: number;
  size?: "sm" | "md";
}

function label(stage: string): string {
  switch (stage) {
    case "chunked":
      return "Indexing";
    case "embedded":
      return "Embedding";
    case "tagged":
      return "Tagging";
    case "summarized":
      return "Summarizing";
    case "entities_extracted":
      return "Entity extraction";
    default:
      return stage;
  }
}

// Subtle status pill. Deliberately doesn't render for "done" — we don't
// want a green checkmark on every card, since that's the common case and
// it would just add visual noise.
export function EnrichmentBadge({ status, itemsAhead, size = "sm" }: Props) {
  if (!status || status.overall === "done" || status.overall === "none") return null;

  const iconSize = size === "sm" ? "w-3 h-3" : "w-3.5 h-3.5";
  const textSize = size === "sm" ? "text-[10px]" : "text-xs";
  const baseCls = `inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${textSize} font-medium`;

  if (status.overall === "failed") {
    const failed = status.failed_stages[0];
    const title = status.last_error
      ? `Failed: ${label(failed || "")} — ${status.last_error}`
      : `Failed: ${label(failed || "")}`;
    return (
      <span
        className={`${baseCls} bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400`}
        title={title}
      >
        <AlertCircle className={iconSize} />
        Failed: {label(failed || "")}
      </span>
    );
  }

  // processing / pending — same visual treatment, subtle difference in copy
  const runningStages = Object.entries(status.stages)
    .filter(([, s]) => s === "running")
    .map(([k]) => k);
  const pendingOnly = runningStages.length === 0;
  const activeLabel = runningStages.length
    ? label(runningStages[0])
    : "Queued";

  const hint =
    pendingOnly && itemsAhead && itemsAhead > 1
      ? `Queued — ~${itemsAhead} items ahead`
      : pendingOnly
        ? "Queued — next up"
        : `Processing: ${runningStages.map(label).join(", ")}`;

  return (
    <span
      className={`${baseCls} bg-sky-50 dark:bg-sky-900/20 text-sky-600 dark:text-sky-400`}
      title={hint}
    >
      {pendingOnly ? <Clock className={iconSize} /> : <Loader2 className={`${iconSize} animate-spin`} />}
      {activeLabel}
    </span>
  );
}
