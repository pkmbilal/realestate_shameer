import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { cache } from "react";

import FavouriteButton from "@/components/favourites/FavouriteButton";
import FavouritesProvider from "@/components/favourites/FavouritesProvider";
import Gallery from "@/components/listings/Gallery";
import ListingLocationMap from "@/components/listings/ListingLocationMap";
import PriceTag from "@/components/listings/PriceTag";
import RegaBadge from "@/components/listings/RegaBadge";
import { listingTitle } from "@/components/listings/title";
import SiteHeader from "@/components/SiteHeader";
import { Link } from "@/i18n/navigation";
import { type Locale, routing } from "@/i18n/routing";
import { api, ApiError, type ListingDetail, toQuery } from "@/lib/api/client";
import { siteUrl } from "@/lib/config";
import { formatNumber, localized } from "@/lib/format";

type Props = { params: Promise<{ locale: string; reference: string }> };

// One API call per page render, shared by generateMetadata and the page (each call is a view).
const loadListing = cache(async (reference: string): Promise<ListingDetail | null> => {
  if (!/^[2-9A-HJ-NP-Z]{8}$/.test(reference)) return null;
  try {
    return await api.listings.detail(reference);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
});

type Translator = (key: string, values?: Record<string, string>) => string;

async function titleFor(listing: ListingDetail, locale: Locale): Promise<string> {
  const tp = await getTranslations({ locale, namespace: "Property" });
  return listingTitle(listing, locale, tp as unknown as Translator);
}

function summary(listing: ListingDetail, locale: string): string {
  const text = localized(listing.description_ar, listing.description_en, locale).replace(/\s+/g, " ");
  return text.length > 160 ? `${text.slice(0, 157)}…` : text;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, reference } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const listing = await loadListing(reference);
  if (!listing) return { robots: { index: false } };

  const title = await titleFor(listing, locale);
  const path = (l: string) => `/${l}/listings/${listing.reference}`;
  const cover = listing.photos[0]?.large_url;
  return {
    title,
    description: summary(listing, locale) || undefined,
    alternates: {
      canonical: path(locale),
      languages: Object.fromEntries(routing.locales.map((l) => [l, path(l)])),
    },
    openGraph: {
      type: "website",
      title,
      url: path(locale),
      locale: locale === "ar" ? "ar_SA" : "en_SA",
      images: cover ? [{ url: cover, width: 1600, height: 1200 }] : undefined,
    },
  };
}

function jsonLd(listing: ListingDetail, locale: string, title: string) {
  const url = `${siteUrl}/${locale}/listings/${listing.reference}`;
  return {
    "@context": "https://schema.org",
    "@type": "RealEstateListing",
    name: title,
    url,
    description: summary(listing, locale) || undefined,
    datePosted: listing.published_at ?? undefined,
    image: listing.photos.map((p) => p.large_url),
    offers:
      listing.price_halalas === null
        ? undefined
        : {
            "@type": "Offer",
            price: Math.round(listing.price_halalas / 100),
            priceCurrency: "SAR",
            businessFunction:
              listing.purpose === "rent"
                ? "http://purl.org/goodrelations/v1#LeaseOut"
                : "http://purl.org/goodrelations/v1#Sell",
          },
    about: {
      "@type": "Accommodation",
      floorSize: { "@type": "QuantitativeValue", value: listing.area_m2, unitCode: "MTK" },
      numberOfBedrooms: listing.bedrooms ?? undefined,
      numberOfBathroomsTotal: listing.bathrooms ?? undefined,
      address: {
        "@type": "PostalAddress",
        addressLocality: localized(listing.city.name_ar, listing.city.name_en, locale),
        addressRegion: listing.district
          ? localized(listing.district.name_ar, listing.district.name_en, locale)
          : undefined,
        addressCountry: "SA",
      },
      geo: { "@type": "GeoCoordinates", latitude: listing.latitude, longitude: listing.longitude },
    },
  };
}

export default async function ListingPage({ params }: Props) {
  const { locale, reference } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const listing = await loadListing(reference);
  if (!listing) notFound();

  const t = await getTranslations("Listing");
  const tp = await getTranslations("Property");
  const title = await titleFor(listing, locale);
  const description = localized(listing.description_ar, listing.description_en, locale);
  const place = [listing.district, listing.city]
    .filter((p) => p !== null)
    .map((p) => localized(p.name_ar, p.name_en, locale))
    .join(locale === "ar" ? "، " : ", ");

  const facts: [string, string][] = [
    [t("facts.type"), tp(`type.${listing.property_type}`)],
    [t("facts.purpose"), tp(`purposeTitle.${listing.purpose}`)],
    [t("facts.area"), tp("area", { area: formatNumber(listing.area_m2, locale) })],
  ];
  if (listing.bedrooms !== null) facts.push([t("facts.beds"), formatNumber(listing.bedrooms, locale)]);
  if (listing.bathrooms !== null) facts.push([t("facts.baths"), formatNumber(listing.bathrooms, locale)]);
  if (listing.furnishing) facts.push([t("facts.furnishing"), tp(`furnishing.${listing.furnishing}`)]);
  facts.push([t("facts.completion"), tp(`completion.${listing.completion}`)]);
  if (listing.rent_period) facts.push([t("facts.rentPeriod"), tp(`rentPeriodName.${listing.rent_period}`)]);

  const advertiser = listing.advertiser;
  const advertiserName = advertiser.broker
    ? localized(advertiser.broker.name_ar, advertiser.broker.name_en, locale)
    : advertiser.agency
      ? localized(advertiser.agency.name_ar, advertiser.agency.name_en, locale)
      : t("advertiserType.owner");

  return (
    <FavouritesProvider>
      <main className="mx-auto flex min-h-dvh max-w-5xl flex-col gap-5 px-4 py-6 sm:px-6">
        <SiteHeader />
        <script
          type="application/ld+json"
          // JSON.stringify output is safe here once "<" is escaped.
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(jsonLd(listing, locale, title)).replace(/</g, "\\u003c"),
          }}
        />

        <Link
          href={`/search${toQuery({ purpose: listing.purpose, city: listing.city.slug_en })}`}
          className="w-fit text-sm font-medium text-emerald-700 hover:underline"
        >
          {t("backToSearch")}
        </Link>

        <Gallery photos={listing.photos} title={title} />

        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-6">
            <header className="flex flex-col gap-2">
              <div className="flex items-start justify-between gap-3">
                <PriceTag
                  halalas={listing.price_halalas}
                  rentPeriod={listing.rent_period}
                  className="text-2xl font-bold text-emerald-800"
                />
                <FavouriteButton reference={listing.reference} variant="button" />
              </div>
              <h1 className="text-xl font-bold sm:text-2xl">{title}</h1>
              <p className="text-slate-600">{place}</p>
              <p className="text-xs text-slate-500">
                {t("reference", { reference: listing.reference })} ·{" "}
                {t("views", { count: listing.view_count })}
              </p>
            </header>

            <dl className="grid grid-cols-2 gap-3 rounded-lg border border-slate-200 p-4 sm:grid-cols-3">
              {facts.map(([label, value]) => (
                <div key={label} className="flex flex-col">
                  <dt className="text-xs text-slate-500">{label}</dt>
                  <dd className="font-medium">{value}</dd>
                </div>
              ))}
            </dl>

            {description && (
              <section className="flex flex-col gap-2">
                <h2 className="text-lg font-bold">{t("description")}</h2>
                <p className="whitespace-pre-line text-slate-700">{description}</p>
              </section>
            )}

            {listing.amenities.length > 0 && (
              <section className="flex flex-col gap-2">
                <h2 className="text-lg font-bold">{t("amenities")}</h2>
                <ul className="flex flex-wrap gap-2">
                  {listing.amenities.map((a) => (
                    <li key={a.id} className="rounded-full bg-slate-100 px-3 py-1 text-sm">
                      {localized(a.name_ar, a.name_en, locale)}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="flex flex-col gap-2">
              <h2 className="text-lg font-bold">{t("location")}</h2>
              <ListingLocationMap lat={listing.latitude} lng={listing.longitude} />
            </section>
          </div>

          <aside className="flex flex-col gap-4">
            <RegaBadge licenceNumber={listing.licence_number} expiresOn={listing.licence_expires_on} />
            <section className="flex flex-col gap-1 rounded-lg border border-slate-200 p-4">
              <h2 className="text-xs text-slate-500">{t("advertiser")}</h2>
              <p className="font-bold">{advertiserName}</p>
              {advertiser.type !== "owner" && (
                <p className="text-sm text-slate-600">{t(`advertiserType.${advertiser.type}`)}</p>
              )}
              {advertiser.broker?.fal_licence && (
                <p className="text-sm text-slate-600">
                  {t("falLicence")}{" "}
                  <bdi dir="ltr" className="font-mono">
                    {advertiser.broker.fal_licence}
                  </bdi>
                </p>
              )}
              {advertiser.broker && advertiser.agency && (
                <p className="text-sm text-slate-600">
                  {localized(advertiser.agency.name_ar, advertiser.agency.name_en, locale)}
                </p>
              )}
              <p className="mt-2 rounded-md bg-slate-50 p-2 text-xs text-slate-500">{t("contactSoon")}</p>
            </section>
          </aside>
        </div>
      </main>
    </FavouritesProvider>
  );
}
