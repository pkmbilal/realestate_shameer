/**
 * The single typed client for the Django API. Components call `api.*` — never `fetch` directly.
 *
 * On the server (inside Docker) requests go to API_INTERNAL_URL (http://api:8000);
 * in the browser they go to NEXT_PUBLIC_API_URL (http://localhost:8000).
 *
 * Login tokens live in httpOnly cookies set by the API, so browser requests send
 * `credentials: "include"`. When the short-lived access cookie expires (401), the client
 * asks /api/auth/refresh/ for a new one once and retries.
 */

const isBrowser = typeof window !== "undefined";

const baseUrl = isBrowser
  ? process.env.NEXT_PUBLIC_API_URL
  : (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL);

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    /** Stable error key from the API (e.g. "invalid_code"), used to pick a translated message. */
    public readonly code?: string,
    public readonly retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = Omit<RequestInit, "body"> & { json?: unknown };

const AUTH_PATHS = ["/api/auth/refresh/", "/api/auth/otp/verify/", "/api/auth/logout/"];

async function send(path: string, { json, ...init }: RequestOptions): Promise<Response> {
  return fetch(`${baseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(json === undefined ? {} : { "Content-Type": "application/json" }),
      ...init.headers,
    },
    body: json === undefined ? undefined : JSON.stringify(json),
  });
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options);

  if (response.status === 401 && isBrowser && !AUTH_PATHS.includes(path)) {
    const refreshed = await send("/api/auth/refresh/", { method: "POST" });
    if (refreshed.ok) response = await send(path, options);
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as {
      code?: string;
      retry_after?: number;
    };
    throw new ApiError(
      response.status,
      `${options.method ?? "GET"} ${path} failed`,
      body.code,
      body.retry_after,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type HealthResponse = {
  status: "ok" | "error";
  portal_name: string;
  checks: Record<string, "ok" | "error">;
};

export type Me = {
  id: number;
  masked_phone: string;
  role: "buyer" | "owner" | "broker" | "agency_admin" | "staff";
  date_joined: string;
};

export const api = {
  health: () => request<HealthResponse>("/api/health/", { cache: "no-store" }),

  me: () => request<Me>("/api/accounts/me/", { cache: "no-store" }),

  auth: {
    requestOtp: (phone: string) =>
      request<{ resend_after: number }>("/api/auth/otp/request/", {
        method: "POST",
        json: { phone },
      }),
    verifyOtp: (phone: string, code: string) =>
      request<Me>("/api/auth/otp/verify/", { method: "POST", json: { phone, code } }),
    logout: () => request<void>("/api/auth/logout/", { method: "POST" }),
  },
};
