import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export function useSharedWithMe() {
  return useQuery<any[]>({
    queryKey: ["shared-with-me"],
    queryFn: () => api.get("/api/v1/shares/shared-with-me"),
  });
}

export function useMyShares() {
  return useQuery<any[]>({
    queryKey: ["shares"],
    queryFn: () => api.get("/api/v1/shares"),
  });
}

export function useCreateShare() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: any) => api.post("/api/v1/shares", data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["shares"] });
      qc.invalidateQueries({ queryKey: ["shared-with-me"] });
    },
  });
}

export function useRevokeShare() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (shareId: string) => api.del(`/api/v1/shares/${shareId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["shares"] }),
  });
}
