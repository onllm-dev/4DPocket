import { apiRequest } from "./api-client";
import type { CheckUrlResponse, ItemRead } from "./types";

export async function saveItem(
  url: string,
  title?: string
): Promise<
  | { status: "saved"; item: ItemRead }
  | { status: "duplicate"; existingId: string; title: string | null }
> {
  const res = await apiRequest("/api/v1/items", {
    method: "POST",
    body: JSON.stringify({ url, title }),
  });

  if (res.status === 409) {
    const data = await res.json();
    return {
      status: "duplicate",
      existingId: data.detail.existing_id,
      title: data.detail?.title || null,
    };
  }

  if (!res.ok) throw new Error(`Save failed: ${res.status}`);
  return { status: "saved", item: await res.json() };
}

export async function checkUrl(url: string): Promise<CheckUrlResponse> {
  const res = await apiRequest(
    `/api/v1/items/check-url?url=${encodeURIComponent(url)}`
  );
  if (!res.ok) throw new Error(`Check failed: ${res.status}`);
  return res.json();
}
