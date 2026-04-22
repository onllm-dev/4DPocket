import { useNavigate } from "react-router-dom";
import type { EntityDetail, RelatedEntity } from "@/hooks/use-entities";
import { typeColor } from "./EntityCard";

const TYPE_FILL: Record<string, string> = {
  person: "#fb7185",
  org: "#a855f7",
  concept: "#0ea5e9",
  tool: "#10b981",
  product: "#f59e0b",
  event: "#d946ef",
  location: "#14b8a6",
  other: "#9ca3af",
};

function fill(t: string): string {
  return TYPE_FILL[t] ?? TYPE_FILL.other;
}

export function RelatedEntitiesMiniGraph({
  entity,
  related,
}: {
  entity: EntityDetail;
  related: RelatedEntity[];
}) {
  const navigate = useNavigate();

  if (related.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-200 dark:border-gray-800 p-6 text-center text-xs text-gray-500 dark:text-gray-400">
        No related entities yet. They appear once enrichment extracts co-occurring entities from more items.
      </div>
    );
  }

  const size = 360;
  const center = size / 2;
  const radius = 130;
  const centerSize = 26;

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 mb-3">
        Related entities
      </h3>
      <div className="flex flex-col md:flex-row gap-4">
        <svg
          viewBox={`0 0 ${size} ${size}`}
          className="w-full md:w-80 h-80 mx-auto"
          role="img"
          aria-label="Related entities radial graph"
        >
          {/* Edges */}
          {related.map((r, i) => {
            const angle = (i / related.length) * 2 * Math.PI - Math.PI / 2;
            const x = center + radius * Math.cos(angle);
            const y = center + radius * Math.sin(angle);
            return (
              <line
                key={`edge-${r.entity.id}`}
                x1={center}
                y1={center}
                x2={x}
                y2={y}
                stroke="#cbd5e1"
                strokeWidth={Math.max(1, Math.min(4, r.relation.weight))}
              />
            );
          })}

          {/* Center node */}
          <circle cx={center} cy={center} r={centerSize} fill={fill(entity.entity_type)} stroke="#0ea5e9" strokeWidth={3} />
          <text x={center} y={center + 4} textAnchor="middle" fontSize="10" fill="#fff" fontWeight="600">
            {entity.canonical_name.slice(0, 5)}
          </text>

          {/* Neighbor nodes */}
          {related.map((r, i) => {
            const angle = (i / related.length) * 2 * Math.PI - Math.PI / 2;
            const x = center + radius * Math.cos(angle);
            const y = center + radius * Math.sin(angle);
            return (
              <g
                key={r.entity.id}
                onClick={() => navigate(`/entities/${r.entity.id}`)}
                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") navigate(`/entities/${r.entity.id}`); }}
                tabIndex={0}
                role="button"
                aria-label={r.entity.canonical_name}
                className="cursor-pointer"
              >
                <circle cx={x} cy={y} r={18} fill={fill(r.entity.entity_type)} opacity={0.9} />
                <text
                  x={x}
                  y={y - 24}
                  textAnchor="middle"
                  fontSize="10"
                  fill="currentColor"
                  className="fill-gray-700 dark:fill-gray-300"
                >
                  {r.entity.canonical_name.length > 14
                    ? r.entity.canonical_name.slice(0, 12) + "…"
                    : r.entity.canonical_name}
                </text>
              </g>
            );
          })}
        </svg>

        <ul className="flex-1 space-y-2 text-sm">
          {related.map((r) => (
            <li
              key={r.entity.id}
              onClick={() => navigate(`/entities/${r.entity.id}`)}
              className="flex items-start gap-2 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
            >
              <span className={`inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] ${typeColor(r.entity.entity_type)}`}>
                {r.entity.entity_type}
              </span>
              <div className="flex-1">
                <div className="font-medium text-gray-900 dark:text-gray-100">
                  {r.entity.canonical_name}
                </div>
                {r.relation.description && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {r.relation.description}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
