// Token stored in localStorage only as a "logged-in" indicator for UI state.
// The actual auth token is in an httpOnly cookie set by the backend.
// Browser automatically sends the cookie with same-origin requests.

const LOGGED_IN_KEY = "4dp_logged_in";

export function isLoggedIn(): boolean {
  return localStorage.getItem(LOGGED_IN_KEY) === "1";
}

export function setLoggedIn(): void {
  localStorage.setItem(LOGGED_IN_KEY, "1");
}

export function clearLoggedIn(): void {
  localStorage.removeItem(LOGGED_IN_KEY);
}

// Create base fetch wrapper - auth handled via httpOnly cookie (browser auto-sends it)
export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const res = await fetch(url, { ...options, headers });

  // Auto-redirect to login on 401 (except for auth endpoints)
  if (res.status === 401 && !url.includes("/auth/")) {
    clearLoggedIn();
    window.location.href = "/login";
  }

  return res;
}

// API helper functions
export const api = {
  async get<T>(url: string): Promise<T> {
    const res = await apiFetch(url);
    if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
    return res.json();
  },

  async post<T>(url: string, body?: unknown): Promise<T> {
    const res = await apiFetch(url, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
    return res.json();
  },

  async patch<T>(url: string, body: unknown): Promise<T> {
    const res = await apiFetch(url, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
    return res.json();
  },

  async del(url: string): Promise<void> {
    const res = await apiFetch(url, { method: "DELETE" });
    if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  },

  async login(identifier: string, password: string): Promise<void> {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: identifier, password }),
      credentials: "include",
    });
    if (!res.ok) throw new Error("Invalid credentials");
    // Token stored in httpOnly cookie by backend; localStorage just tracks login state
    setLoggedIn();
  },

  async logout(): Promise<void> {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" });
    clearLoggedIn();
  },

  async register(
    email: string,
    password: string,
    displayName?: string,
    username?: string,
  ): Promise<unknown> {
    return this.post("/api/v1/auth/register", {
      email,
      username: username || email.split("@")[0],
      password,
      display_name: displayName,
    });
  },
};
