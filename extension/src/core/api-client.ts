import { STORAGE_KEYS } from "./constants";
import type { StoredAuth } from "./types";

// Storage adapter - injected at runtime by each browser context
let storageAdapter: {
  get(keys: string[]): Promise<Record<string, unknown>>;
  set(items: Record<string, unknown>): Promise<void>;
  remove(keys: string[]): Promise<void>;
};

export function setStorageAdapter(adapter: typeof storageAdapter): void {
  storageAdapter = adapter;
}

export async function getStoredAuth(): Promise<StoredAuth> {
  const data = await storageAdapter.get([
    STORAGE_KEYS.serverUrl,
    STORAGE_KEYS.token,
    STORAGE_KEYS.username,
  ]);
  return {
    serverUrl: (data[STORAGE_KEYS.serverUrl] as string) || "",
    token: (data[STORAGE_KEYS.token] as string) || null,
    username: (data[STORAGE_KEYS.username] as string) || null,
  };
}

export async function setStoredAuth(auth: Partial<StoredAuth>): Promise<void> {
  const items: Record<string, unknown> = {};
  if (auth.serverUrl !== undefined) items[STORAGE_KEYS.serverUrl] = auth.serverUrl;
  if (auth.token !== undefined) items[STORAGE_KEYS.token] = auth.token;
  if (auth.username !== undefined) items[STORAGE_KEYS.username] = auth.username;
  await storageAdapter.set(items);
}

export async function clearStoredAuth(): Promise<void> {
  await storageAdapter.remove([STORAGE_KEYS.token, STORAGE_KEYS.username]);
}

export async function apiRequest(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const { serverUrl, token } = await getStoredAuth();
  if (!serverUrl) throw new Error("Server not configured");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return fetch(`${serverUrl}${path}`, { ...options, headers });
}
