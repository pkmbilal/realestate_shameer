import { ApiError } from "@/lib/api/client";

/** Error codes the listing API can send that have their own message in "Dashboard.errors". */
const KNOWN = [
  "invalid_licence_number",
  "not_found",
  "licence_expired",
  "licence_not_yours",
  "licence_in_use",
  "unsupported_city",
  "nafath_required",
  "broker_profile_required",
  "agency_profile_required",
  "not_an_advertiser",
  "advertiser_required",
  "not_editable",
  "invalid_status",
  "incomplete",
  "unsupported_photo_type",
  "photo_too_large",
  "too_many_photos",
  "photo_not_uploaded",
  "upload_failed",
  "invalid",
] as const;

export type DashboardErrorKey = (typeof KNOWN)[number] | "generic";

function isKnown(code: string): code is (typeof KNOWN)[number] {
  return (KNOWN as readonly string[]).includes(code);
}

/** The "Dashboard.errors" key to show for an error from the API (or "generic"). */
export function dashboardErrorKey(error: unknown): DashboardErrorKey {
  if (error instanceof ApiError) {
    if (error.code && isKnown(error.code)) return error.code;
    if (error.status === 400 && Object.keys(error.fieldErrors).length > 0) return "invalid";
  }
  return "generic";
}

/** Fields the API may list as still missing before a listing can be submitted. */
export const MISSING_FIELDS = ["price_halalas", "rent_period", "title", "photos"] as const;
export type MissingField = (typeof MISSING_FIELDS)[number];

export function isMissingField(name: string): name is MissingField {
  return (MISSING_FIELDS as readonly string[]).includes(name);
}
