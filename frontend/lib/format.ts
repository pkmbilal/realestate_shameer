/**
 * Number and price formatting. Arabic pages use Latin digits (common on Saudi property
 * sites and easier to compare); change NUMBER_SYSTEM to "arab" for Arabic-Indic digits.
 */

const NUMBER_SYSTEM = "latn";

function intlLocale(locale: string): string {
  return locale === "ar" ? `ar-SA-u-nu-${NUMBER_SYSTEM}` : "en-SA";
}

export function formatNumber(value: number, locale: string): string {
  return new Intl.NumberFormat(intlLocale(locale)).format(value);
}

/** 85_000_000 halalas → "SAR 850,000" / "‏850,000 ر.س.‏" */
export function formatSar(halalas: number, locale: string): string {
  return new Intl.NumberFormat(intlLocale(locale), {
    style: "currency",
    currency: "SAR",
    maximumFractionDigits: 0,
  }).format(Math.round(halalas / 100));
}

/** With halalas, for payments and invoices: 1_030_450 → "SAR 10,304.50". */
export function formatSarExact(halalas: number, locale: string): string {
  return new Intl.NumberFormat(intlLocale(locale), {
    style: "currency",
    currency: "SAR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(halalas / 100);
}

/** Short price for map pins: 850K, 1.2M. */
export function formatSarShort(halalas: number, locale: string): string {
  return new Intl.NumberFormat(intlLocale(locale), {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Math.round(halalas / 100));
}

export function formatDate(iso: string, locale: string): string {
  return new Intl.DateTimeFormat(intlLocale(locale), {
    dateStyle: "medium",
    timeZone: "Asia/Riyadh",
  }).format(new Date(iso));
}

/** Pick the field for the page language, falling back to the other one. */
export function localized(ar: string, en: string, locale: string): string {
  return (locale === "ar" ? ar || en : en || ar) ?? "";
}
