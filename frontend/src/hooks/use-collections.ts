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
