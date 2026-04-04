import { apiRequest } from "./api-client";
import type { HighlightRead } from "./types";

export interface CreateHighlightPayload {
  item_id: string;
  text: string;
  note?: string;
  color?: string;
  position?: {
    selector: string;
    textOffset: number;
    textLength: number;
    context: string;
  };
}

export async function createHighlight(
  payload: CreateHighlightPayload
): Promise<HighlightRead> {
  const res = await apiRequest("/api/v1/highlights", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Create highlight failed: ${res.status}`);
  return res.json();
}

export async function getHighlightsForItem(
  itemId: string
): Promise<HighlightRead[]> {
  const res = await apiRequest(
    `/api/v1/highlights?item_id=${encodeURIComponent(itemId)}`
  );
  if (!res.ok) throw new Error(`Get highlights failed: ${res.status}`);
  return res.json();
}
