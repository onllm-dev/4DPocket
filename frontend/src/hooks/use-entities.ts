import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface EntitySynthesisContext {
  context: string;
  source_item_id: string | null;
  source_title?: string | null;
}

export interface EntitySynthesisRelationship {
  entity_name: string;
  nature: string;
}

export interface EntitySynthesis {
  summary: string;
  themes: string[];
  key_contexts: EntitySynthesisContext[];
  relationships: EntitySynthesisRelationship[];
  confidence: "low" | "medium" | "high";
  last_updated: string;
  source_item_count: number;
}

export interface EntitySummary {
  id: string;
  canonical_name: string;
  entity_type: string;
  description: string | null;
  item_count: number;
  has_synthesis?: boolean;
  synthesis_confidence?: string | null;
  created_at: string | null;
}

export interface EntityDetail extends EntitySummary {
  aliases: { alias: string; source: string }[];
  synthesis: EntitySynthesis | null;
  synthesis_generated_at: string | null;
  synthesis_confidence: string | null;
  synthesis_item_count: number;
  updated_at: string | null;
}

export interface RelatedEntity {
  entity: {
    id: string;
    canonical_name: string;
    entity_type: string;
    item_count: number;
  };
  relation: {
    keywords: string | null;
    description: string | null;
    weight: number;
    item_count: number;
  };
}

export interface EntityGraphNode {
  id: string;
  name: string;
  entity_type: string;
  item_count: number;
  has_synthesis: boolean;
}

export interface EntityGraphEdge {
  id: string;
  source: string;
  target: string;
  keywords: string | null;
  weight: number;
}

export interface EntityGraphResponse {
  nodes: EntityGraphNode[];
  edges: EntityGraphEdge[];
}

export function useEntities(params: { entity_type?: string; q?: string; limit?: number } = {}) {
  const qs = new URLSearchParams();
  if (params.entity_type) qs.set("entity_type", params.entity_type);
  if (params.q) qs.set("q", params.q);
  qs.set("limit", String(params.limit ?? 200));
  const qsStr = qs.toString();
  return useQuery<EntitySummary[]>({
    queryKey: ["entities", params],
    queryFn: () => api.get(`/api/v1/entities?${qsStr}`),
  });
}

export function useEntityDetail(id: string | undefined) {
  return useQuery<EntityDetail>({
    queryKey: ["entity", id],
    queryFn: () => api.get(`/api/v1/entities/${id}`),
    enabled: !!id,
  });
}

export function useRelatedEntities(id: string | undefined, limit = 12) {
  return useQuery<RelatedEntity[]>({
    queryKey: ["entity-related", id, limit],
    queryFn: () => api.get(`/api/v1/entities/${id}/related?limit=${limit}`),
    enabled: !!id,
  });
}

export function useEntityGraph(entityType?: string) {
  const qs = new URLSearchParams();
  if (entityType) qs.set("entity_type", entityType);
  qs.set("limit", "300");
  return useQuery<EntityGraphResponse>({
    queryKey: ["entity-graph", entityType],
    queryFn: () => api.get(`/api/v1/entities/graph?${qs.toString()}`),
  });
}

export function useRegenerateSynthesis() {
  const qc = useQueryClient();
  return useMutation<{ status: string; synthesis: EntitySynthesis }, Error, { id: string; force?: boolean }>({
    mutationFn: ({ id, force }) => api.post(`/api/v1/entities/${id}/synthesize${force ? "?force=true" : ""}`),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["entity", vars.id] });
      qc.invalidateQueries({ queryKey: ["entities"] });
    },
  });
}
