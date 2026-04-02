const TOKEN_KEY = "4dp_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

// Create base fetch wrapper with auth + 401 redirect
export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...options, headers });

  // Auto-redirect to login on 401
  if (res.status === 401 && !url.includes("/auth/")) {
    clearToken();
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

  async login(email: string, password: string): Promise<string> {
    const res = await fetch("/api/v1/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username: email, password }),
    });
    if (!res.ok) throw new Error("Invalid credentials");
    const data = await res.json();
    setToken(data.access_token);
    return data.access_token;
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
