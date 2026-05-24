import { apiRequest } from "./api-client";
import type { CheckUrlResponse, ItemRead } from "./types";

export async function saveItem(
  url: string,
  title?: string
): Promise<
  | { status: "saved"; item: ItemRead }
  | { status: "duplicate"; existingId: string; title: string | null }
> {
  let step = "apiRequest";
  try {
    const res = await apiRequest("/api/v1/items", {
      method: "POST",
      body: JSON.stringify({ url, title }),
    });

    if (res.status === 409) {
      step = "res.json-409";
      const data = await res.json();
      const detail = typeof data.detail === "object" && data.detail !== null
        ? data.detail
        : null;
      return {
        status: "duplicate",
        existingId: detail?.existing_id ?? "",
        title: detail?.title ?? null,
      };
    }

    if (!res.ok) throw new Error(`Save failed: ${res.status}`);
    step = "res.json-200";
    const item = await res.json();
    return { status: "saved", item };
  } catch (err) {
    throw new Error(`save failed at ${step}: ${(err as Error).message}`);
  }
}

export async function checkUrl(url: string): Promise<CheckUrlResponse> {
  const res = await apiRequest(
    `/api/v1/items/check-url?url=${encodeURIComponent(url)}`
  );
  if (!res.ok) throw new Error(`Check failed: ${res.status}`);
  return res.json();
}
