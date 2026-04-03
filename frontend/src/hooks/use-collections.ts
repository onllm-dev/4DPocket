import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

interface Collection {
  id: string;
  name: string;
  description: string | null;
  icon: string | null;
  is_public: boolean;
  created_at: string;
}

export function useCollections() {
  return useQuery<Collection[]>({
    queryKey: ["collections"],
    queryFn: () => api.get("/api/v1/collections"),
  });
}

export function useCreateCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      api.post<Collection>("/api/v1/collections", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collections"] }),
  });
}

export function useDeleteCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/collections/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collections"] }),
  });
}

export function useCollection(id: string) {
  return useQuery<Collection>({
    queryKey: ["collection", id],
    queryFn: () => api.get(`/api/v1/collections/${id}`),
    enabled: !!id,
  });
}

export function useAddItemToCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ collectionId, itemIds }: { collectionId: string; itemIds: string[] }) =>
      api.post(`/api/v1/collections/${collectionId}/items`, { item_ids: itemIds }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      qc.invalidateQueries({ queryKey: ["collection", vars.collectionId] });
      qc.invalidateQueries({ queryKey: ["item-collections"] });
    },
  });
}

export function useRemoveItemFromCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ collectionId, itemId }: { collectionId: string; itemId: string }) =>
      api.del(`/api/v1/collections/${collectionId}/items/${itemId}`),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      qc.invalidateQueries({ queryKey: ["collection", vars.collectionId] });
      qc.invalidateQueries({ queryKey: ["item-collections"] });
    },
  });
}

export function useAddNoteToCollection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ collectionId, noteIds }: { collectionId: string; noteIds: string[] }) =>
      api.post(`/api/v1/collections/${collectionId}/notes`, { note_ids: noteIds }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["collections"] });
      qc.invalidateQueries({ queryKey: ["collection", vars.collectionId] });
    },
  });
}

export function useItemCollections(itemId: string) {
  return useQuery<Collection[]>({
    queryKey: ["item-collections", itemId],
    queryFn: () => api.get(`/api/v1/items/${itemId}/collections`),
    enabled: !!itemId,
  });
}
