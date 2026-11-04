import { ApiError } from "@/lib/api/client";

export type LeadErrorKey = "rateLimited" | "notActive" | "generic";

/** Translation key (under Leads.errors) for a failed lead request. */
export function errorKey(err: unknown): LeadErrorKey {
  if (err instanceof ApiError) {
    if (err.status === 429) return "rateLimited";
    if (err.status === 404) return "notActive";
  }
  return "generic";
}
