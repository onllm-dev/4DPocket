import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface Highlight {
  id: string;
  text: string;
  color: string;
  position: { start: number; end: number } | null;
}

export function useHighlights(itemId?: string, noteId?: string) {
  return useQuery<Highlight[]>({
    queryKey: ["highlights", itemId, noteId],
    queryFn: () =>
      api.get(
        `/api/v1/highlights?${itemId ? `item_id=${itemId}` : `note_id=${noteId}`}`
      ),
    enabled: !!(itemId || noteId),
  });
}
