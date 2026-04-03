import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface Feed {
  id: string;
  url: string;
  title: string | null;
  category: string | null;
  target_collection_id: string | null;
  poll_interval: number;
  format: string;
  mode: string;
  filters: string | null;
  is_active: boolean;
  last_fetched_at: string | null;
  created_at: string;
}

export interface FeedEntry {
  id: string;
  feed_id: string;
  title: string | null;
  url: string | null;
  content_snippet: string | null;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

export function useFeeds() {
  return useQuery<Feed[]>({
    queryKey: ["feeds"],
    queryFn: () => api.get("/api/v1/rss"),
  });
}

export function useCreateFeed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      url: string;
      title?: string;
      category?: string;
      target_collection_id?: string;
      poll_interval?: number;
      format?: string;
      mode?: string;
      filters?: string;
    }) => api.post<Feed>("/api/v1/rss", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feeds"] }),
  });
}

export function useUpdateFeed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Partial<Feed>) =>
      api.patch<Feed>(`/api/v1/rss/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feeds"] }),
  });
}

export function useDeleteFeed() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/rss/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feeds"] }),
  });
}

export function useFeedEntries(feedId: string) {
  return useQuery<FeedEntry[]>({
    queryKey: ["feed-entries", feedId],
    queryFn: () => api.get(`/api/v1/rss/${feedId}/entries`),
    enabled: !!feedId,
  });
}

export function useApproveFeedEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ feedId, entryId }: { feedId: string; entryId: string }) =>
      api.post(`/api/v1/rss/${feedId}/entries/${entryId}/approve`),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["feed-entries", vars.feedId] });
      qc.invalidateQueries({ queryKey: ["items"] });
    },
  });
}

export function useRejectFeedEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ feedId, entryId }: { feedId: string; entryId: string }) =>
      api.patch(`/api/v1/rss/${feedId}/entries/${entryId}`, { status: "rejected" }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["feed-entries", vars.feedId] });
    },
  });
}
