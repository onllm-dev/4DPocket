import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface ApiTokenSummary {
  id: string;
  name: string;
  prefix: string;
  role: "viewer" | "editor";
  all_collections: boolean;
  collection_ids: string[];
  include_uncollected: boolean;
  allow_deletion: boolean;
  admin_scope: boolean;
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface CreateTokenRequest {
  name: string;
  role: "viewer" | "editor";
  all_collections: boolean;
  collection_ids: string[];
  include_uncollected: boolean;
  allow_deletion: boolean;
  admin_scope: boolean;
  expires_in_days: number | null;
}

export interface CreateTokenResponse extends ApiTokenSummary {
  token: string;
}

export function useApiTokens() {
  return useQuery<ApiTokenSummary[]>({
    queryKey: ["api-tokens"],
    queryFn: () => api.get("/api/v1/auth/tokens"),
  });
}

export function useCreateApiToken() {
  const qc = useQueryClient();
  return useMutation<CreateTokenResponse, Error, CreateTokenRequest>({
    mutationFn: (payload) => api.post("/api/v1/auth/tokens", payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-tokens"] }),
  });
}

export function useRevokeApiToken() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (tokenId) => api.del(`/api/v1/auth/tokens/${tokenId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-tokens"] }),
  });
}

export function useRevokeAllApiTokens() {
  const qc = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: async () => {
      await api.post("/api/v1/auth/tokens/revoke-all");
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-tokens"] }),
  });
}
