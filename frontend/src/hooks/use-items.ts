import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface EnrichmentStatus {
  overall: "none" | "pending" | "processing" | "done" | "failed";
  stages: Record<string, string>;
  failed_stages: string[];
  last_error: string | null;
}

interface Item {
  id: string;
  user_id: string;
  item_type: string;
  source_platform: string;
  url: string | null;
  title: string | null;
  description: string | null;
  content: string | null;
  raw_content: string | null;
  summary: string | null;
  favicon_url: string | null;
  media: Array<{ type: string; url?: string; role: string; local_path?: string; original_url?: string }>;
  item_metadata: Record<string, unknown>;
  is_favorite: boolean;
  is_archived: boolean;
  reading_progress: number;
  reading_status: "unread" | "reading_list" | "read";
  read_at: string | null;
  created_at: string;
  updated_at: string;
  enrichment_status?: EnrichmentStatus | null;
}

export interface QueueStats {
  items_in_flight: number;
  running_items: number;
  pending_items: number;
}

export function useQueueStats() {
  return useQuery<QueueStats>({
    queryKey: ["queue-stats"],
    queryFn: () => api.get("/api/v1/items/queue-stats"),
    // Poll every 10s while any UI is mounted — cheap query, single row count.
    refetchInterval: 10_000,
    staleTime: 5_000,
  });
}

interface ItemFilters {
  item_type?: string;
  source_platform?: string;
  is_favorite?: boolean;
  is_archived?: boolean;
  tag_id?: string;
  sort_by?: string;
  sort_order?: string;
}

export function useItems(filters: ItemFilters = {}) {
  return useInfiniteQuery<Item[]>({
    queryKey: ["items", filters],
    queryFn: async ({ pageParam = 0 }) => {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, val]) => {
        if (val !== undefined && val !== null) params.set(key, String(val));
      });
      params.set("offset", String(pageParam));
      params.set("limit", "20");
      return api.get(`/api/v1/items?${params.toString()}`);
    },
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === 20 ? allPages.length * 20 : undefined,
    initialPageParam: 0,
  });
}

export function useItem(id: string) {
  return useQuery<Item>({
    queryKey: ["item", id],
    queryFn: () => api.get(`/api/v1/items/${id}`),
    enabled: !!id,
    // Don't retry 404s — the "Item not found" state should appear immediately.
    retry: (failureCount, err) =>
      failureCount < 1 && !(err instanceof Error && /404/.test(err.message)),
  });
}

export function useCreateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { url?: string; title?: string; content?: string }) =>
      api.post<Item>("/api/v1/items", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["items"] }),
  });
}

export function useUpdateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Partial<Item>) =>
      api.patch<Item>(`/api/v1/items/${id}`, data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["items"] });
      qc.invalidateQueries({ queryKey: ["item", vars.id] });
    },
  });
}

export function useDeleteItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/items/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["items"] }),
  });
}

export function useSearch(query: string) {
  return useQuery<Item[]>({
    queryKey: ["search", query],
    queryFn: () => api.get(`/api/v1/search?q=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
  });
}
