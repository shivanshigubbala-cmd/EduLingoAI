/**
 * Auth API client — thin wrappers around backend endpoints.
 *
 * Expected backend endpoints:
 *   POST /auth/signup   { name, email, password }        → 201 + Set-Cookie (httpOnly JWT)
 *   POST /auth/login    { email, password }               → 200 + Set-Cookie (httpOnly JWT)
 *   POST /auth/logout                                       → 200, clears cookie
 *   GET  /auth/me                                           → 200 { id, email, name } (requires cookie)
 *
 * The JWT is set as an httpOnly secure cookie by the backend.
 * The frontend never reads or stores the token — the browser carries it automatically.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  if (!res.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = await res.json();
      if (body.detail) message = body.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new AuthError(message, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export async function signup(payload: {
  name: string;
  email: string;
  password: string;
}) {
  return request<{ id: string; email: string; name: string }>(
    "/auth/signup",
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export async function login(payload: { email: string; password: string }) {
  return request<{ id: string; email: string; name: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function logout() {
  return request<void>("/auth/logout", { method: "POST" });
}

export async function getMe() {
  return request<{ id: string; email: string; name: string }>("/auth/me");
}

export { AuthError };
