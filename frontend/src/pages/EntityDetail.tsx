import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Calendar } from "lucide-react";
import {
  useEntityDetail,
  useRegenerateSynthesis,
  useRelatedEntities,
} from "@/hooks/use-entities";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { typeColor } from "@/components/entities/EntityCard";
import { SynthesisPanel } from "@/components/entities/SynthesisPanel";
import { RelatedEntitiesMiniGraph } from "@/components/entities/RelatedEntitiesMiniGraph";

interface EntityItem {
  id: string;
  title: string | null;
  url: string | null;
  summary: string | null;
  created_at: string | null;
  salience: number;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function EntityDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: entity, isLoading, error } = useEntityDetail(id);
  const { data: related } = useRelatedEntities(id);
  const regenerate = useRegenerateSynthesis();

  const { data: items } = useQuery<EntityItem[]>({
    queryKey: ["entity-items", id],
    queryFn: () => api.get(`/api/v1/entities/${id}/items?limit=20`),
    enabled: !!id,
  });

  if (isLoading) {
    return <p className="p-6 text-sm text-gray-500">Loading entity…</p>;
  }
  if (error || !entity) {
    return <p className="p-6 text-sm text-red-500">Entity not found.</p>;
  }

  const regenError =
    regenerate.isError ? regenerate.error?.message ?? "Regeneration failed" : null;

  return (
    <div className="animate-fade-in max-w-5xl mx-auto">
      <Link
        to="/entities"
        className="inline-flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 mb-4"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Knowledge Graph
      </Link>

      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {entity.canonical_name}
          </h1>
          <span className={`inline-block px-2 py-1 rounded-md text-xs font-medium ${typeColor(entity.entity_type)}`}>
            {entity.entity_type}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span>{entity.item_count} mention{entity.item_count === 1 ? "" : "s"}</span>
          {entity.aliases.length > 0 && (
            <span>Also known as: {entity.aliases.slice(0, 4).map((a) => a.alias).join(", ")}</span>
          )}
          {entity.updated_at && (
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              Updated {formatDate(entity.updated_at)}
            </span>
          )}
        </div>
        {entity.description && (
          <p className="mt-3 text-sm text-gray-700 dark:text-gray-300 max-w-2xl">
            {entity.description}
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <SynthesisPanel
            synthesis={entity.synthesis}
            generatedAt={entity.synthesis_generated_at}
            entityMentions={entity.item_count}
            onRegenerate={() =>
              regenerate.mutate({ id: entity.id, force: entity.synthesis !== null })
            }
            regenerating={regenerate.isPending}
            error={regenError}
          />

          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">
              Linked knowledge
            </h2>
            {(items?.length ?? 0) === 0 ? (
              <p className="text-sm text-gray-500">No items linked yet.</p>
            ) : (
              <ul className="space-y-2">
                {items!.map((it) => (
                  <li key={it.id}>
                    <Link
                      to={`/item/${it.id}`}
                      className="block p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                    >
                      <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {it.title || "Untitled"}
                      </div>
                      {it.summary && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2">
                          {it.summary}
                        </p>
                      )}
                      <div className="text-[10px] text-gray-400 mt-0.5">
                        {formatDate(it.created_at)} · salience {it.salience.toFixed(2)}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div>
          <RelatedEntitiesMiniGraph entity={entity} related={related ?? []} />
        </div>
      </div>
    </div>
  );
}
