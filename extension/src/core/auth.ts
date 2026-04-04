import { apiRequest, getStoredAuth, setStoredAuth, clearStoredAuth } from "./api-client";
import type { UserRead } from "./types";

export async function testConnection(serverUrl: string): Promise<boolean> {
  try {
    const res = await fetch(`${serverUrl}/api/v1/health`);
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
  // Login uses form-encoded body (OAuth2 spec)
  const res = await fetch(`${serverUrl}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(res.status === 401 ? "Invalid credentials" : `Login failed: ${text}`);
  }

  const data = await res.json();
  const token = data.access_token;

  // Store auth
  await setStoredAuth({ serverUrl, token });

  // Fetch user info
  const user = await validateToken();
  if (!user) throw new Error("Failed to validate token after login");

  await setStoredAuth({ username: user.username });
  return user;
}

export async function validateToken(): Promise<UserRead | null> {
  try {
    const res = await apiRequest("/api/v1/auth/me");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
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
