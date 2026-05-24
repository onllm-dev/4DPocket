import { apiRequest, getStoredAuth, setStoredAuth, clearStoredAuth } from "./api-client";
import type { UserRead } from "./types";

export async function testConnection(serverUrl: string): Promise<boolean> {
  try {
    const res = await fetch(serverUrl + "/api/v1/health");
    if (!res.ok) return false;
    const data = await res.json();
    return data.status === "ok";
  } catch {
    return false;
  }
}

export async function login(
  serverUrl: string,
  username: string,
  password: string
): Promise<UserRead> {
  const res = await fetch(serverUrl + "/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  });

  if (!res.ok) {
    throw new Error(res.status === 401 ? "Invalid credentials" : "Login failed. Please check your server URL and try again.");
  }

  const data = await res.json();
  const token = data.access_token;

  await setStoredAuth({ serverUrl, token });

  const serverUrlClean = serverUrl.replace(/\/+$/, "");
  const meRes = await fetch(serverUrlClean + "/api/v1/auth/me", {
    headers: { Authorization: "Bearer " + token },
  });
  if (!meRes.ok) throw new Error("Failed to validate token after login");
  const user = await meRes.json();

  await setStoredAuth({ username: user.username });
  return user;
}

export async function validateToken(): Promise<UserRead | null> {
  const { serverUrl, token } = await getStoredAuth();
  if (!serverUrl || !token) return null;
  const url = serverUrl.replace(/\/+$/, "") + "/api/v1/auth/me";
  let meRes: Response;
  try {
    meRes = await fetch(url, {
      headers: { Authorization: "Bearer " + token },
    });
  } catch (err) {
    console.warn("[4dp] validateToken fetch failed:", err);
    return null;
  }
  if (!meRes.ok) return null;
  return await meRes.json();
}

export async function logout(): Promise<void> {
  try {
    await apiRequest("/api/v1/auth/logout", { method: "POST" });
  } catch {
    // Best effort
  }
  await clearStoredAuth();
}

export async function isAuthenticated(): Promise<boolean> {
  const { token } = await getStoredAuth();
  if (!token) return false;
  const user = await validateToken();
  if (!user) {
    await clearStoredAuth();
    return false;
  }
  return true;
}