/**
 * The single typed client for the Django API. Components call `api.*` — never `fetch` directly.
 *
 * On the server (inside Docker) requests go to API_INTERNAL_URL (http://api:8000);
 * in the browser they go to NEXT_PUBLIC_API_URL (http://localhost:8000).
 */

const baseUrl =
  typeof window === "undefined"
    ? (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL)
    : process.env.NEXT_PUBLIC_API_URL;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new ApiError(response.status, `${init?.method ?? "GET"} ${path} failed`);
  }
  return (await response.json()) as T;
}

export type HealthResponse = {
  status: "ok" | "error";
  portal_name: string;
  checks: Record<string, "ok" | "error">;
};

export const api = {
  health: () => request<HealthResponse>("/api/health/", { cache: "no-store" }),
};
