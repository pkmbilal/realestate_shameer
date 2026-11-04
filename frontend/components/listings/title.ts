import { useLocale, useTranslations } from "next-intl";

import type { ListingCard } from "@/lib/api/client";
import { localized } from "@/lib/format";

/** The bits of next-intl's translator that listingTitle needs ("Property" namespace). */
type PropertyTranslator = (key: string, values?: Record<string, string>) => string;

/** The listing fields a title is built from (public cards and the advertiser's own listings). */
type Titled = Pick<
  ListingCard,
  "title_ar" | "title_en" | "property_type" | "purpose" | "city" | "district"
>;

/**
 * The advertiser's title in the page language, or a generated one such as
 * "Apartment for sale in Al Shulah, Dammam" when they left it empty.
 */
export function listingTitle(listing: Titled, locale: string, t: PropertyTranslator): string {
  const own = localized(listing.title_ar, listing.title_en, locale);
  if (own) return own;
  const place = listing.district
    ? localized(listing.district.name_ar, listing.district.name_en, locale)
    : localized(listing.city.name_ar, listing.city.name_en, locale);
  return t("defaultTitle", {
    type: t(`type.${listing.property_type}`),
    purpose: t(`purpose.${listing.purpose}`),
    place,
  });
}

export function useListingTitle(listing: Titled): string {
  const t = useTranslations("Property");
  const locale = useLocale();
  return listingTitle(listing, locale, t as unknown as PropertyTranslator);
}
