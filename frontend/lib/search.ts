import {
  PROPERTY_TYPES,
  type Completion,
  type Furnishing,
  type Purpose,
  type PropertyType,
  type RentPeriod,
  type SearchParams,
  type SortKey,
} from "@/lib/api/client";

/** Raw Next.js `searchParams` (each value may be a string, an array or missing). */
export type RawSearchParams = Record<string, string | string[] | undefined>;

export type SearchView = "list" | "map";

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function oneOf<T extends string>(value: string | undefined, allowed: readonly T[]): T | undefined {
  return allowed.find((item) => item === value);
}

function wholeNumber(value: string | undefined): number | undefined {
  if (!value || !/^\d{1,11}$/.test(value)) return undefined;
  return Number(value);
}

function slug(value: string | undefined): string | undefined {
  return value && /^[a-z0-9-]{1,100}$/.test(value) ? value : undefined;
}

/**
 * Reads the page URL into API search params, silently dropping anything invalid so a
 * hand-edited URL never breaks the page.
 */
export function parseSearchParams(raw: RawSearchParams): SearchParams {
  const types = (Array.isArray(raw.type) ? raw.type.join(",") : (raw.type ?? ""))
    .split(",")
    .map((t) => oneOf<PropertyType>(t, PROPERTY_TYPES))
    .filter((t): t is PropertyType => t !== undefined);

  const params: SearchParams = {
    purpose: oneOf<Purpose>(first(raw.purpose), ["sale", "rent"]),
    type: types.length ? types : undefined,
    city: slug(first(raw.city)),
    district: slug(first(raw.district)),
    price_min: wholeNumber(first(raw.price_min)),
    price_max: wholeNumber(first(raw.price_max)),
    beds_min: wholeNumber(first(raw.beds_min)),
    baths_min: wholeNumber(first(raw.baths_min)),
    area_min: wholeNumber(first(raw.area_min)),
    area_max: wholeNumber(first(raw.area_max)),
    completion: oneOf<Completion>(first(raw.completion), ["ready", "off_plan"]),
    furnishing: oneOf<Furnishing>(first(raw.furnishing), [
      "unfurnished",
      "semi_furnished",
      "furnished",
    ]),
    rent_period: oneOf<RentPeriod>(first(raw.rent_period), ["yearly", "monthly"]),
    sort: oneOf<SortKey>(first(raw.sort), ["newest", "price_asc", "price_desc"]),
    page: wholeNumber(first(raw.page)),
  };
  if (params.district && !params.city) params.district = undefined;
  if (params.purpose !== "rent") params.rent_period = undefined;
  if (params.page !== undefined && params.page < 1) params.page = undefined;
  return params;
}

export function parseView(raw: RawSearchParams): SearchView {
  return first(raw.view) === "map" ? "map" : "list";
}
