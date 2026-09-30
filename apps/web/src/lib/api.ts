/**
 * Thin fetch wrapper for the backend. All calls go through the Next proxy at
 * `/api/backend/*` (see next.config.ts) so cookies stay first-party.
 */

const BASE = "/api/backend";

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  // De-duplicate concurrent refreshes.
  if (!refreshing) {
    refreshing = rawFetch("/auth/refresh", { method: "POST" })
      .then((r) => r.ok)
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export async function api<T>(path: string, init: RequestInit = {}, _retry = true): Promise<T> {
  let res = await rawFetch(path, init);

  // Access token expired: refresh once, then retry the original request.
  if (res.status === 401 && _retry && !path.startsWith("/auth/refresh")) {
    const body = await res.clone().json().catch(() => null);
    if (body?.error?.code === "token_expired" && (await tryRefresh())) {
      res = await rawFetch(path, init);
    }
  }

  const text = await res.text();
  const body = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiError(
      res.status,
      err.code ?? "error",
      err.message ?? res.statusText,
      err.details ?? {},
    );
  }
  return body as T;
}
