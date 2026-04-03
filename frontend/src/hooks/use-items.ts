import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

interface Item {
  id: string;
  user_id: string;
  item_type: string;
  source_platform: string;
  url: string | null;
  title: string | null;
  description: string | null;
  content: string | null;
  summary: string | null;
  media: Array<{ type: string; url?: string; role: string; local_path?: string; original_url?: string }>;
  item_metadata: Record<string, unknown>;
  is_favorite: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
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
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== null) params.set(key, String(val));
  });

  return useInfiniteQuery<Item[]>({
    queryKey: ["items", filters],
    queryFn: async ({ pageParam = 0 }) => {
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
