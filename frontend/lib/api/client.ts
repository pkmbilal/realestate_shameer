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
    /** Form validation errors from DRF: field name → error messages. */
    public readonly fieldErrors: Record<string, string[]> = {},
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
    const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    const { code, detail, retry_after, ...rest } = body;
    const fieldErrors = Object.fromEntries(
      Object.entries(rest).filter(([, value]) => Array.isArray(value)),
    ) as Record<string, string[]>;
    throw new ApiError(
      response.status,
      `${options.method ?? "GET"} ${path} failed`,
      // Our views send {code}; DRF permission errors send {detail} (e.g. "nafath_required").
      typeof code === "string" ? code : typeof detail === "string" ? detail : undefined,
      typeof retry_after === "number" ? retry_after : undefined,
      fieldErrors,
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
  is_nafath_verified: boolean;
};

export type NafathStatus = "pending" | "approved" | "rejected" | "expired";

export type NafathStart = {
  transaction_ref: string;
  /** The number the user taps in the Nafath app. */
  random_number: string;
  status: NafathStatus;
};

export type AgencySummary = { id: number; name_ar: string; name_en: string; logo_url: string };

export type BrokerProfileInput = {
  name_ar: string;
  name_en: string;
  photo_url: string;
  fal_licence: string;
  whatsapp: string;
  city_ids: number[];
};

export type BrokerProfile = BrokerProfileInput & { id: number; agency: AgencySummary | null };

export type LatLng = { lat: number; lng: number };

export type City = {
  id: number;
  name_ar: string;
  name_en: string;
  slug_ar: string;
  slug_en: string;
  region: string;
  center: LatLng | null;
};

export type District = Omit<City, "region">;

// --- Listings and search ------------------------------------------------------------

export type Purpose = "sale" | "rent";
export type RentPeriod = "yearly" | "monthly";
export type PropertyType =
  | "apartment"
  | "villa"
  | "floor"
  | "duplex"
  | "townhouse"
  | "land"
  | "building";
export type Furnishing = "unfurnished" | "semi_furnished" | "furnished";
export type Completion = "ready" | "off_plan";
export type SortKey = "newest" | "price_asc" | "price_desc";

export const PROPERTY_TYPES: readonly PropertyType[] = [
  "apartment",
  "villa",
  "floor",
  "duplex",
  "townhouse",
  "land",
  "building",
];

/** Query for /api/listings/. Prices are whole SAR; the API converts them to halalas. */
export type SearchParams = {
  purpose?: Purpose;
  type?: PropertyType[];
  city?: string;
  district?: string;
  price_min?: number;
  price_max?: number;
  beds_min?: number;
  baths_min?: number;
  area_min?: number;
  area_max?: number;
  completion?: Completion;
  furnishing?: Furnishing;
  rent_period?: RentPeriod;
  sort?: SortKey;
  /** minLng,minLat,maxLng,maxLat */
  bbox?: string;
  page?: number;
};

export type PlaceRef = { id: number; name_ar: string; name_en: string; slug_en: string };

export type Photo = { id: number; position: number; card_url: string; large_url: string };

export type Amenity = { id: number; slug: string; name_ar: string; name_en: string };

export type ListingCard = {
  reference: string;
  purpose: Purpose;
  property_type: PropertyType;
  price_halalas: number | null;
  rent_period: RentPeriod | "";
  bedrooms: number | null;
  bathrooms: number | null;
  area_m2: number;
  title_ar: string;
  title_en: string;
  city: PlaceRef;
  district: PlaceRef | null;
  latitude: number;
  longitude: number;
  cover: Photo | null;
  is_featured: boolean;
  published_at: string | null;
};

export type Advertiser = {
  type: "broker" | "agency" | "owner";
  broker: {
    id: number;
    name_ar: string;
    name_en: string;
    photo_url: string;
    fal_licence: string;
  } | null;
  agency: AgencySummary | null;
};

export type ListingDetail = ListingCard & {
  furnishing: Furnishing | "";
  completion: Completion;
  description_ar: string;
  description_en: string;
  licence_number: string;
  licence_expires_on: string;
  photos: Photo[];
  amenities: Amenity[];
  advertiser: Advertiser;
  view_count: number;
};

export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type MapPin = {
  reference: string;
  latitude: number;
  longitude: number;
  price_halalas: number | null;
  purpose: Purpose;
  rent_period: RentPeriod | "";
  is_featured: boolean;
};

/** Builds "?a=1&type=villa,land" from a params object, skipping empty values. */
export function toQuery(params: Record<string, unknown>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      if (value.length) query.set(key, value.join(","));
    } else {
      query.set(key, String(value));
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export const api = {
  health: () => request<HealthResponse>("/api/health/", { cache: "no-store" }),

  locations: {
    // Cities and districts change rarely; Next.js may reuse the answer for 10 minutes.
    cities: () => request<City[]>("/api/locations/cities/", { next: { revalidate: 600 } }),
    districts: (citySlug: string) =>
      request<District[]>(`/api/locations/cities/${encodeURIComponent(citySlug)}/districts/`, {
        next: { revalidate: 600 },
      }),
  },

  me: () => request<Me>("/api/accounts/me/", { cache: "no-store" }),

  listings: {
    search: (params: SearchParams) =>
      request<Page<ListingCard>>(`/api/listings/${toQuery(params)}`, { cache: "no-store" }),
    map: (params: SearchParams & { bbox: string }) =>
      request<{ results: MapPin[]; truncated: boolean }>(`/api/listings/map/${toQuery(params)}`),
    /** Each call counts as a page view, so call it once per page render. */
    detail: (reference: string) =>
      request<ListingDetail>(`/api/listings/${encodeURIComponent(reference)}/`, {
        cache: "no-store",
      }),
  },

  favourites: {
    list: (page = 1) =>
      request<Page<ListingCard>>(`/api/listings/favourites/${toQuery({ page })}`, {
        cache: "no-store",
      }),
    references: () =>
      request<{ references: string[] }>("/api/listings/favourites/ids/", { cache: "no-store" }),
    add: (reference: string) =>
      request<void>(`/api/listings/${encodeURIComponent(reference)}/favourite/`, {
        method: "PUT",
      }),
    remove: (reference: string) =>
      request<void>(`/api/listings/${encodeURIComponent(reference)}/favourite/`, {
        method: "DELETE",
      }),
  },

  nafath: {
    // The national ID is sent to the API only; never store or log it in the browser.
    start: (nationalId: string) =>
      request<NafathStart>("/api/accounts/nafath/start/", {
        method: "POST",
        json: { national_id: nationalId },
      }),
    status: (transactionRef: string) =>
      request<{ status: NafathStatus }>("/api/accounts/nafath/status/", {
        method: "POST",
        json: { transaction_ref: transactionRef },
      }),
  },

  brokers: {
    me: () => request<BrokerProfile>("/api/brokers/me/", { cache: "no-store" }),
    saveMe: (profile: BrokerProfileInput) =>
      request<BrokerProfile>("/api/brokers/me/", { method: "PUT", json: profile }),
  },

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
