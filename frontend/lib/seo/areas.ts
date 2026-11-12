/**
 * SEO area pages: /{locale}/{purpose}/{type}/{city?}/{district?}
 *   /ar/للإيجار/شقق/الدمام/الشعلة  ↔  /en/rent/apartments/dammam/al-shulah
 *
 * The purpose and type segments are fixed constants, NOT translations: a public URL must
 * never change because someone reworded a label. City and district segments come from the
 * slug_ar / slug_en fields in the locations app.
 */
import type { Locale } from "@/i18n/routing";
import {
  api,
  type AreaCount,
  type AreaPlace,
  type City,
  type District,
  type PropertyType,
  type Purpose,
} from "@/lib/api/client";

type SegmentMap<K extends string> = Record<K, Record<Locale, string>>;

export const PURPOSE_SEGMENTS: SegmentMap<Purpose> = {
  rent: { en: "rent", ar: "للإيجار" },
  sale: { en: "sale", ar: "للبيع" },
};

export const TYPE_SEGMENTS: SegmentMap<PropertyType> = {
  apartment: { en: "apartments", ar: "شقق" },
  villa: { en: "villas", ar: "فلل" },
  floor: { en: "floors", ar: "أدوار" },
  duplex: { en: "duplexes", ar: "دوبلكس" },
  townhouse: { en: "townhouses", ar: "تاون-هاوس" },
  land: { en: "land", ar: "أراضي" },
  building: { en: "buildings", ar: "عمائر" },
};

/** A city or district as carried on cities, districts, listing refs and area-count rows. */
type Slugs = { slug_en: string; slug_ar: string; name_en: string; name_ar: string };

export type Area = {
  purpose: Purpose;
  type: PropertyType;
  city?: Slugs;
  district?: Slugs;
};

export type ResolvedArea = {
  purpose: Purpose;
  type: PropertyType;
  city: City | null;
  district: District | null;
  /** The locale whose slugs the URL was written in (may differ from the page locale). */
  slugLocale: Locale;
};

function decode(segment: string): string {
  try {
    return decodeURIComponent(segment).normalize("NFC");
  } catch {
    return segment;
  }
}

function lookup<K extends string>(map: SegmentMap<K>, segment: string, locale: Locale) {
  return (Object.keys(map) as K[]).find((key) => map[key][locale] === segment);
}

const slugOf = (place: Slugs, locale: Locale) => (locale === "ar" ? place.slug_ar : place.slug_en);

/** The path of an area page without the locale prefix, e.g. "/rent/apartments/dammam". */
export function areaPath(locale: Locale, area: Area): string {
  const parts = [PURPOSE_SEGMENTS[area.purpose][locale], TYPE_SEGMENTS[area.type][locale]];
  if (area.city) {
    parts.push(slugOf(area.city, locale));
    if (area.district) parts.push(slugOf(area.district, locale));
  }
  return `/${parts.join("/")}`;
}

/** Full path with the locale prefix, for canonical URLs, hreflang and sitemaps. */
export function localizedAreaPath(locale: Locale, area: Area): string {
  return `/${locale}${areaPath(locale, area)}`;
}

/** Same area, without the most specific place (district → city → whole province). */
export function parentArea(area: Area): Area | null {
  if (area.district) return { ...area, district: undefined };
  if (area.city) return { ...area, city: undefined };
  return null;
}

/**
 * Turns URL segments into an area, or null when any segment is unknown.
 * Slugs written in the other language are accepted too (the language switcher keeps the
 * path as it is), so the page can redirect them to the right language's URL.
 */
export async function resolveArea(
  rawPurpose: string,
  rawType: string,
  rawPlace: string[] = [],
): Promise<ResolvedArea | null> {
  if (rawPlace.length > 2) return null;
  const purposeSeg = decode(rawPurpose);
  const typeSeg = decode(rawType);
  const citySeg = rawPlace[0] === undefined ? undefined : decode(rawPlace[0]);
  const districtSeg = rawPlace[1] === undefined ? undefined : decode(rawPlace[1]);

  for (const slugLocale of ["ar", "en"] as const) {
    const purpose = lookup(PURPOSE_SEGMENTS, purposeSeg, slugLocale);
    const type = lookup(TYPE_SEGMENTS, typeSeg, slugLocale);
    if (!purpose || !type) continue;
    if (citySeg === undefined) return { purpose, type, city: null, district: null, slugLocale };

    const cities = await api.locations.cities();
    const city = cities.find((c) => slugOf(c, slugLocale) === citySeg);
    if (!city) return null;
    if (districtSeg === undefined) return { purpose, type, city, district: null, slugLocale };

    const districts = await api.locations.districts(city.slug_en);
    const district = districts.find((d) => slugOf(d, slugLocale) === districtSeg);
    if (!district) return null;
    return { purpose, type, city, district, slugLocale };
  }
  return null;
}

export function toArea(resolved: ResolvedArea): Area {
  return {
    purpose: resolved.purpose,
    type: resolved.type,
    city: resolved.city ?? undefined,
    district: resolved.district ?? undefined,
  };
}

/** Area-count rows convert to Areas directly. */
export function rowToArea(row: AreaCount): Area {
  return {
    purpose: row.purpose,
    type: row.type,
    city: row.city ?? undefined,
    district: row.district ?? undefined,
  };
}

/** True when the row is exactly this purpose/type at this city/district level. */
export function sameArea(row: AreaCount, area: Area): boolean {
  return (
    row.purpose === area.purpose &&
    row.type === area.type &&
    row.city?.slug_en === area.city?.slug_en &&
    row.district?.slug_en === area.district?.slug_en
  );
}

export function placeName(place: AreaPlace | City | District, locale: Locale): string {
  return locale === "ar" ? place.name_ar : place.name_en;
}
