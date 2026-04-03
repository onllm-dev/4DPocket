import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

interface Item {
  id: string;
  title: string | null;
  description: string | null;
  url: string | null;
  favicon_url?: string | null;
  source_platform: string;
  item_type: string;
  summary: string | null;
  media: Array<{ type: string; url?: string; role: string; local_path?: string }>;
  is_favorite: boolean;
  reading_status: string;
  reading_progress: number;
  created_at: string;
  tags?: Array<{ id: string; name: string; color?: string | null }>;
}

export function useReadingList() {
  return useQuery<Item[]>({
    queryKey: ["reading-list"],
    queryFn: () => api.get("/api/v1/items/reading-list"),
  });
}

export function useReadList() {
  return useQuery<Item[]>({
    queryKey: ["read-list"],
    queryFn: () => api.get("/api/v1/items/read"),
  });
}

export function useToggleReadingList() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, type, add }: { id: string; type: "item" | "note"; add: boolean }) => {
      const endpoint = type === "item" ? `/api/v1/items/${id}` : `/api/v1/notes/${id}`;
      return api.patch(endpoint, {
        reading_status: add ? "reading_list" : "unread",
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reading-list"] });
      qc.invalidateQueries({ queryKey: ["read-list"] });
      qc.invalidateQueries({ queryKey: ["items"] });
      qc.invalidateQueries({ queryKey: ["notes"] });
    },
  });
}

export function useMarkAsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, type }: { id: string; type: "item" | "note" }) => {
      const endpoint = type === "item" ? `/api/v1/items/${id}` : `/api/v1/notes/${id}`;
      return api.patch(endpoint, { reading_status: "read" });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reading-list"] });
      qc.invalidateQueries({ queryKey: ["read-list"] });
      qc.invalidateQueries({ queryKey: ["items"] });
      qc.invalidateQueries({ queryKey: ["notes"] });
    },
  });
}
