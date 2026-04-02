import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

interface Tag {
  id: string;
  name: string;
  slug: string;
  parent_id: string | null;
  ai_generated: boolean;
  color: string | null;
  usage_count: number;
  created_at: string;
}

export function useTags() {
  return useQuery<Tag[]>({
    queryKey: ["tags"],
    queryFn: () => api.get("/api/v1/tags"),
  });
}

export function useCreateTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; color?: string; parent_id?: string }) =>
      api.post<Tag>("/api/v1/tags", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tags"] }),
  });
}

export function useDeleteTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/tags/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tags"] }),
  });
}
