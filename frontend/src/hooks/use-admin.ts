import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useAdminUsers() {
  return useQuery<any[]>({
    queryKey: ["admin", "users"],
    queryFn: () => api.get("/api/v1/admin/users"),
  });
}

export function useAdminSettings() {
  return useQuery<any>({
    queryKey: ["admin", "settings"],
    queryFn: () => api.get("/api/v1/admin/settings"),
  });
}

export function useUpdateAdminSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) => api.patch("/api/v1/admin/settings", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "settings"] }),
  });
}

export function useUpdateAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; role?: string; is_active?: boolean }) =>
      api.patch(`/api/v1/admin/users/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "users"] }),
  });
}
