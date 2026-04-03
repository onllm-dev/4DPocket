import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface Note {
  id: string;
  user_id: string;
  item_id: string | null;
  title: string | null;
  content: string | null;
  summary: string | null;
  is_favorite: boolean;
  is_archived: boolean;
  reading_status: "unread" | "reading_list" | "read";
  reading_progress: number;
  created_at: string;
  updated_at: string;
}

interface Tag {
  id: string;
  name: string;
  slug: string;
  color: string | null;
}

export function useNotes(filters: { is_archived?: boolean; is_favorite?: boolean } = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== null) params.set(key, String(val));
  });

  return useQuery<Note[]>({
    queryKey: ["notes", filters],
    queryFn: () => api.get(`/api/v1/notes?${params.toString()}`),
  });
}

export function useNote(id: string) {
  return useQuery<Note>({
    queryKey: ["note", id],
    queryFn: () => api.get(`/api/v1/notes/${id}`),
    enabled: !!id,
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { title?: string; content: string; item_id?: string; tags?: string[] }) =>
      api.post<Note>("/api/v1/notes", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes"] }),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string } & Partial<Note>) =>
      api.patch<Note>(`/api/v1/notes/${id}`, data),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["notes"] });
      qc.invalidateQueries({ queryKey: ["note", vars.id] });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/v1/notes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notes"] }),
  });
}

export function useNoteTags(noteId: string) {
  return useQuery<Tag[]>({
    queryKey: ["note-tags", noteId],
    queryFn: () => api.get(`/api/v1/notes/${noteId}/tags`),
    enabled: !!noteId,
  });
}

export function useAddNoteTags() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, tags }: { noteId: string; tags: string[] }) =>
      api.post(`/api/v1/notes/${noteId}/tags`, { tags }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["note-tags", vars.noteId] });
    },
  });
}

export function useRemoveNoteTag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ noteId, tagId }: { noteId: string; tagId: string }) =>
      api.del(`/api/v1/notes/${noteId}/tags/${tagId}`),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ["note-tags", vars.noteId] });
    },
  });
}

export function useSummarizeNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (noteId: string) => api.post(`/api/v1/notes/${noteId}/summarize`),
    onSuccess: (_, noteId) => {
      qc.invalidateQueries({ queryKey: ["note", noteId] });
      qc.invalidateQueries({ queryKey: ["notes"] });
    },
  });
}

export function useGenerateNoteTitle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (noteId: string) => api.post(`/api/v1/notes/${noteId}/generate-title`),
    onSuccess: (_, noteId) => {
      qc.invalidateQueries({ queryKey: ["note", noteId] });
      qc.invalidateQueries({ queryKey: ["notes"] });
    },
  });
}

export function useSearchNotes(query: string) {
  return useQuery<Note[]>({
    queryKey: ["notes-search", query],
    queryFn: () => api.get(`/api/v1/notes/search?q=${encodeURIComponent(query)}`),
    enabled: query.length >= 2,
  });
}
