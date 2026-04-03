import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface ItemLink {
  id: string;
  item_id: string;
  url: string;
  title: string | null;
  domain: string | null;
  position: number;
  created_at: string;
}

export function useItemLinks(itemId: string) {
  return useQuery<ItemLink[]>({
    queryKey: ["item-links", itemId],
    queryFn: () => api.get(`/api/v1/items/${itemId}/links`),
    enabled: !!itemId,
  });
}

export function useAddItemLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, ...data }: { itemId: string; url: string; title?: string }) =>
      api.post<ItemLink>(`/api/v1/items/${itemId}/links`, data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["item-links", vars.itemId] });
    },
  });
}

export function useRemoveItemLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, linkId }: { itemId: string; linkId: string }) =>
      api.del(`/api/v1/items/${itemId}/links/${linkId}`),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["item-links", vars.itemId] });
    },
  });
}

export function useReorderItemLinks() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, linkIds }: { itemId: string; linkIds: string[] }) =>
      api.post(`/api/v1/items/${itemId}/links/reorder`, { link_ids: linkIds }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["item-links", vars.itemId] });
    },
  });
}
