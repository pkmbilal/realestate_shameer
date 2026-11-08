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
    const { code, detail, retry_after, fields, ...rest } = body;
    const fieldErrors = Object.fromEntries(
      Object.entries(rest).filter(([, value]) => Array.isArray(value)),
    ) as Record<string, string[]>;
    // Our service errors send {code: "invalid", fields: {name: "required"}}.
    if (fields && typeof fields === "object") {
      for (const [name, error] of Object.entries(fields as Record<string, unknown>)) {
        if (typeof error === "string") fieldErrors[name] = [error];
      }
    }
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

// --- Advertiser dashboard ("my listings") --------------------------------------------

export type ListingStatus =
  | "draft"
  | "pending_review"
  | "active"
  | "expired"
  | "taken_down"
  | "archived";

/** Statuses in which the advertiser may still edit the listing and its photos. */
export const EDITABLE_STATUSES: readonly ListingStatus[] = ["draft", "pending_review", "active"];

/** The fields the advertiser fills in. Everything else comes from REGA and is read-only. */
export type MyListingInput = {
  price_halalas: number | null;
  rent_period: RentPeriod | "";
  bedrooms: number | null;
  bathrooms: number | null;
  furnishing: Furnishing | "";
  completion: Completion;
  title_ar: string;
  title_en: string;
  description_ar: string;
  description_en: string;
  amenity_ids: number[];
};

export type MyListing = MyListingInput & {
  id: number;
  reference: string;
  status: ListingStatus;
  moderation_note: string;
  /** What is still needed before submitting: "price_halalas", "rent_period", "title", "photos". */
  missing_fields: string[];
  licence_number: string;
  licence_expires_on: string;
  purpose: Purpose;
  property_type: PropertyType;
  area_m2: number;
  city: PlaceRef;
  district: PlaceRef | null;
  latitude: number;
  longitude: number;
  photos: Photo[];
  published_at: string | null;
  /** When it last moved to the top of "newest" (first publish or a paid refresh). */
  refreshed_at: string | null;
  post_expires_at: string | null;
  featured_until: string | null;
  view_count: number;
  lead_count: number;
  created_at: string;
  updated_at: string;
};

// --- Credits wallet ---

export type WalletAction = "post" | "refresh" | "feature";

/** What an action costs. 0 credits means it is free right now. `days` is used by "feature". */
export type CreditPrice = { action: WalletAction; credits: number; days: number };

export type WalletSummary = {
  /** Owners post for free and have no wallet. */
  has_wallet: boolean;
  balance: number;
  prices: CreditPrice[];
};

export type CreditTransactionKind = "grant" | "topup" | "spend" | "refund" | "adjustment";

export type CreditTransaction = {
  id: number;
  kind: CreditTransactionKind;
  action: WalletAction | "";
  /** Positive adds credits, negative takes them. */
  amount: number;
  balance_after: number;
  /** Listing reference, if the entry is about a listing. */
  listing: string | null;
  note: string;
  created_at: string;
};

// --- Top-ups and invoices ---

/** A credit pack on sale. Price in halalas (1 SAR = 100), VAT included. */
export type TopUpPackage = {
  id: number;
  name_ar: string;
  name_en: string;
  credits: number;
  price_halalas: number;
};

export type PaymentStatus = "pending" | "paid" | "failed" | "expired";

export type TopUp = {
  id: number;
  status: PaymentStatus;
  credits: number;
  amount_halalas: number;
  package_name_ar: string;
  package_name_en: string;
  /** The wallet balance right now. */
  balance: number;
  /** Set once the e-invoice has been issued (shortly after payment). */
  invoice_id: number | null;
  paid_at: string | null;
  created_at: string;
};

export type Invoice = {
  id: number;
  number: string;
  issued_at: string;
  credits: number;
  total_halalas: number;
  vat_halalas: number;
};

/** A short-lived URL to PUT one photo straight into file storage. */
export type PhotoUpload = {
  key: string;
  upload_url: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_in: number;
};

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

// --- Leads -----------------------------------------------------------------------------

function mine(reference: string): string {
  return `/api/listings/mine/${encodeURIComponent(reference)}/`;
}

/**
 * Upload one file straight to file storage using a URL from `api.myListings.presignPhoto`.
 * This is the only request that does not go to our API, so it lives here with the client.
 */
export async function uploadToStorage(upload: PhotoUpload, file: File): Promise<void> {
  const response = await fetch(upload.upload_url, {
    method: upload.method,
    headers: upload.headers,
    body: file,
  });
  if (!response.ok) throw new ApiError(response.status, "photo upload failed", "upload_failed");
}

export type LeadChannel = "whatsapp" | "call" | "form";

export type LeadInput = {
  listing: string;
  channel: LeadChannel;
  locale: string;
  name?: string;
  phone?: string;
  message?: string;
};

/** The contact link comes back only after the lead is logged; it is never in listing data. */
export type LeadCreated = {
  id: number;
  channel: LeadChannel;
  whatsapp_url?: string;
  tel_url?: string;
};

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

  /** The logged-in broker's or agency's credits. Needs a Nafath-verified advertiser. */
  wallet: {
    get: () => request<WalletSummary>("/api/wallet/", { cache: "no-store" }),
    transactions: (page = 1) =>
      request<Page<CreditTransaction>>(`/api/wallet/transactions/${toQuery({ page })}`, {
        cache: "no-store",
      }),
  },

  /** Buying credits. The browser is sent to the gateway's checkout page, then comes back. */
  topUps: {
    packages: () => request<TopUpPackage[]>("/api/payments/packages/", { cache: "no-store" }),
    start: (packageId: number, locale: string) =>
      request<{ payment_id: number; checkout_url: string }>("/api/payments/top-ups/", {
        method: "POST",
        json: { package_id: packageId, locale },
      }),
    /** Also asks the gateway for news if the payment is still pending. */
    get: (id: number) =>
      request<TopUp>(`/api/payments/top-ups/${id}/`, { cache: "no-store" }),
  },

  invoices: {
    list: (page = 1) =>
      request<Page<Invoice>>(`/api/invoices/${toQuery({ page })}`, { cache: "no-store" }),
    /** A link the browser can open to download the PDF (sent with the login cookie). */
    pdfUrl: (id: number) => `${baseUrl}/api/invoices/${id}/pdf/`,
  },

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
    amenities: () => request<Amenity[]>("/api/listings/amenities/", { cache: "no-store" }),
  },

  /** The logged-in advertiser's own listings. Needs a Nafath-verified owner/broker/agency. */
  myListings: {
    list: () => request<MyListing[]>("/api/listings/mine/", { cache: "no-store" }),
    get: (reference: string) =>
      request<MyListing>(mine(reference), { cache: "no-store" }),
    /** Start a draft from a REGA ad licence; REGA fills in type, area, location, etc. */
    start: (licenceNumber: string) =>
      request<MyListing>("/api/listings/mine/", {
        method: "POST",
        json: { licence_number: licenceNumber },
      }),
    update: (reference: string, input: Partial<MyListingInput>) =>
      request<MyListing>(mine(reference), { method: "PATCH", json: input }),
    submit: (reference: string) =>
      request<MyListing>(`${mine(reference)}submit/`, { method: "POST" }),
    archive: (reference: string) =>
      request<MyListing>(`${mine(reference)}archive/`, { method: "POST" }),
    /** Spend credits to move a live listing back to the top of "newest". */
    refresh: (reference: string) =>
      request<MyListing>(`${mine(reference)}refresh/`, { method: "POST" }),
    /** Spend credits to pin a live listing on top of search for a few days. */
    feature: (reference: string) =>
      request<MyListing>(`${mine(reference)}feature/`, { method: "POST" }),
    presignPhoto: (reference: string, file: { type: string; size: number }) =>
      request<PhotoUpload>(`${mine(reference)}photos/presign/`, {
        method: "POST",
        json: { content_type: file.type, size_bytes: file.size },
      }),
    /** Call after the file has been uploaded to the presigned URL. */
    confirmPhoto: (reference: string, key: string) =>
      request<Photo>(`${mine(reference)}photos/`, { method: "POST", json: { key } }),
    /** The first photo becomes the cover. */
    reorderPhotos: (reference: string, photoIds: number[]) =>
      request<MyListing>(`${mine(reference)}photos/`, {
        method: "PUT",
        json: { photo_ids: photoIds },
      }),
    deletePhoto: (reference: string, photoId: number) =>
      request<void>(`${mine(reference)}photos/${photoId}/`, { method: "DELETE" }),
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

  leads: {
    create: (lead: LeadInput) =>
      request<LeadCreated>("/api/leads/", { method: "POST", json: lead }),
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
