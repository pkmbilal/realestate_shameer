/**
 * SEO area page: /{locale}/{purpose}/{type}/{city?}/{district?}
 * e.g. /ar/للإيجار/شقق/الدمام/الشعلة and /en/rent/apartments/dammam/al-shulah
 *
 * Static routes (search, listings, dashboard, …) take priority over this dynamic one, so it
 * only sees paths that are not a known page; anything that is not a real area is a 404.
 */
import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { cache } from "react";

import FavouritesProvider from "@/components/favourites/FavouritesProvider";
import ListingCard from "@/components/listings/ListingCard";
import Pagination from "@/components/search/Pagination";
import Breadcrumbs, { type Crumb } from "@/components/seo/Breadcrumbs";
import SiteHeader from "@/components/SiteHeader";
import { Link } from "@/i18n/navigation";
import { type Locale, routing } from "@/i18n/routing";
import {
  api,
  type AreaCount,
  type ListingCard as Card,
  type Page,
  toQuery,
} from "@/lib/api/client";
import { formatNumber } from "@/lib/format";
import {
  type Area,
  areaPath,
  localizedAreaPath,
  placeName,
  resolveArea,
  type ResolvedArea,
  rowToArea,
  toArea,
} from "@/lib/seo/areas";
import {
  absoluteUrl,
  jsonLdHtml,
  languageAlternates,
  openGraph,
  robotsFor,
} from "@/lib/seo/meta";
import { areaTitle, areaTitleParts } from "@/lib/seo/titles";

const PAGE_SIZE = 20; // matches ListingPagination on the API

type Props = {
  params: Promise<{ locale: string; purpose: string; type: string; place?: string[] }>;
  searchParams: Promise<{ page?: string | string[] }>;
};

function pageNumber(raw: string | string[] | undefined): number {
  const n = Number(Array.isArray(raw) ? raw[0] : raw);
  return Number.isInteger(n) && n > 1 ? n : 1;
}

// Shared by generateMetadata and the page within one request.
const loadArea = cache(
  async (purpose: string, type: string, place: string[] | undefined) => {
    try {
      return await resolveArea(purpose, type, place);
    } catch {
      return null; // locations API down: treat as not found rather than crash
    }
  },
);

const loadResults = cache(async (area: ResolvedArea, page: number): Promise<Page<Card> | null> => {
  try {
    return await api.listings.search({
      purpose: area.purpose,
      type: [area.type],
      city: area.city?.slug_en,
      district: area.district?.slug_en,
      page,
    });
  } catch {
    return null;
  }
});

async function loadAreaCounts(): Promise<AreaCount[]> {
  try {
    return await api.seo.areas();
  } catch {
    return [];
  }
}

function withPage(path: string, page: number): string {
  return page > 1 ? `${path}?page=${page}` : path;
}

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { locale, purpose, type, place } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const resolved = await loadArea(purpose, type, place);
  if (!resolved) return { robots: robotsFor(false) };

  const page = pageNumber((await searchParams).page);
  const area = toArea(resolved);
  const results = await loadResults(resolved, page);
  const count = results?.count ?? 0;
  const ta = await getTranslations({ locale, namespace: "Area" });
  const title = await areaTitle(locale, area);
  const description = ta("description", { ...(await areaTitleParts(locale, area)), count });
  const url = withPage(localizedAreaPath(locale, area), page);
  const cover = results?.results.find((listing) => listing.cover)?.cover;

  return {
    title,
    description,
    alternates: {
      canonical: url,
      languages: languageAlternates((l) => withPage(localizedAreaPath(l, area), page)),
    },
    // Empty areas are thin content: keep them out of the index but let crawlers follow links.
    robots: robotsFor(count > 0),
    openGraph: openGraph(locale, {
      title,
      description,
      url,
      image: cover ? { url: cover.large_url, width: 1600, height: 1200 } : null,
    }),
  };
}

export default async function AreaPage({ params, searchParams }: Props) {
  const { locale, purpose, type, place } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const resolved = await loadArea(purpose, type, place);
  if (!resolved) notFound();
  const area = toArea(resolved);
  const page = pageNumber((await searchParams).page);

  // URL written with the other language's slugs (e.g. after switching language): send the
  // visitor and search engines to this language's own URL.
  if (resolved.slugLocale !== locale) {
    permanentRedirect(encodeURI(withPage(localizedAreaPath(locale, area), page)));
  }

  const [results, counts] = await Promise.all([loadResults(resolved, page), loadAreaCounts()]);
  const pages = results ? Math.max(1, Math.ceil(results.count / PAGE_SIZE)) : 1;
  if (results && page > pages) notFound();

  const t = await getTranslations("Area");
  const ts = await getTranslations("Search");
  const title = await areaTitle(locale, area);

  const crumbs = await breadcrumbs(locale, resolved);
  const children = childAreas(counts, area);
  const related = await relatedLinks(locale, counts, area);
  const refineQuery = toQuery({
    purpose: area.purpose,
    type: [area.type],
    city: area.city?.slug_en,
    district: area.district?.slug_en,
  });

  const itemList = results?.results.length
    ? {
        "@context": "https://schema.org",
        "@type": "ItemList",
        name: title,
        itemListElement: results.results.map((listing, index) => ({
          "@type": "ListItem",
          position: (page - 1) * PAGE_SIZE + index + 1,
          url: absoluteUrl(`/${locale}/listings/${listing.reference}`),
        })),
      }
    : null;

  return (
    <FavouritesProvider>
      <main className="mx-auto flex min-h-dvh max-w-7xl flex-col gap-5 px-4 py-6 sm:px-6">
        <SiteHeader />
        {itemList && <script type="application/ld+json" dangerouslySetInnerHTML={jsonLdHtml(itemList)} />}

        <Breadcrumbs locale={locale} items={crumbs} />

        <header className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <p className="text-sm font-medium text-slate-700">
              {results ? ts("results", { count: results.count }) : ""}
            </p>
            <Link
              href={`/search${refineQuery}`}
              className="text-sm font-medium text-emerald-700 hover:underline"
            >
              {t("refine")}
            </Link>
          </div>
        </header>

        {children.length > 0 && (
          <section className="flex flex-col gap-2">
            <h2 className="text-base font-bold">{area.city ? t("byDistrict") : t("byCity")}</h2>
            <ul className="flex flex-wrap gap-2">
              {children.map((row) => {
                const child = rowToArea(row);
                const placeRow = row.district ?? row.city;
                return (
                  <li key={areaPath("en", child)}>
                    <Link
                      href={areaPath(locale, child)}
                      className="inline-flex items-center gap-2 rounded-full border border-slate-300 px-3 py-1.5 text-sm hover:border-emerald-600 hover:bg-emerald-50"
                    >
                      <span>{placeRow ? placeName(placeRow, locale) : ""}</span>
                      <span className="rounded-full bg-slate-100 px-2 text-xs text-slate-600">
                        {formatNumber(row.count, locale)}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        <section>
          {results === null ? (
            <p className="rounded-lg bg-red-50 p-4 text-red-700">{ts("loadError")}</p>
          ) : results.results.length === 0 ? (
            <p className="rounded-lg bg-slate-50 p-4 text-slate-600">{t("empty")}</p>
          ) : (
            <>
              <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {results.results.map((listing) => (
                  <li key={listing.reference}>
                    <ListingCard listing={listing} />
                  </li>
                ))}
              </ul>
              <Pagination page={page} pages={pages} query={{}} basePath={areaPath(locale, area)} />
            </>
          )}
        </section>

        {related.length > 0 && (
          <section className="flex flex-col gap-2 border-t border-slate-200 pt-5">
            <h2 className="text-base font-bold">{t("otherTypes")}</h2>
            <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {related.map((link) => (
                <li key={link.href}>
                  <Link href={link.href} className="text-sm text-emerald-700 hover:underline">
                    {link.label} ({formatNumber(link.count, locale)})
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </FavouritesProvider>
  );
}

/** Purpose+type › city › district; the last one is the current page (no link). */
async function breadcrumbs(locale: Locale, resolved: ResolvedArea): Promise<Crumb[]> {
  const base: Area = { purpose: resolved.purpose, type: resolved.type };
  const levels: Area[] = [base];
  if (resolved.city) levels.push({ ...base, city: resolved.city });
  if (resolved.city && resolved.district) {
    levels.push({ ...base, city: resolved.city, district: resolved.district });
  }
  const tp = await getTranslations({ locale, namespace: "Property" });
  return levels.map((level, index) => {
    const label =
      index === 0
        ? `${tp(`typePlural.${level.type}`)} ${tp(`purpose.${level.purpose}`)}`
        : index === 1 && resolved.city
          ? placeName(resolved.city, locale)
          : resolved.district
            ? placeName(resolved.district, locale)
            : "";
    const isLast = index === levels.length - 1;
    return { label, href: isLast ? undefined : areaPath(locale, level) };
  });
}

/** One level down: the cities of a province-wide page, the districts of a city page. */
function childAreas(counts: AreaCount[], area: Area): AreaCount[] {
  if (area.district) return [];
  return counts.filter(
    (row) =>
      row.purpose === area.purpose &&
      row.type === area.type &&
      (area.city
        ? row.city?.slug_en === area.city.slug_en && row.district !== null
        : row.city !== null && row.district === null),
  );
}

/** Same place: other property types with the same purpose, and this type with the other purpose. */
async function relatedLinks(locale: Locale, counts: AreaCount[], area: Area) {
  const samePlace = (row: AreaCount) =>
    row.city?.slug_en === area.city?.slug_en && row.district?.slug_en === area.district?.slug_en;
  const rows = counts.filter(
    (row) =>
      samePlace(row) &&
      ((row.purpose === area.purpose && row.type !== area.type) ||
        (row.purpose !== area.purpose && row.type === area.type)),
  );
  return Promise.all(
    rows.map(async (row) => {
      const related = rowToArea(row);
      return {
        href: areaPath(locale, related),
        label: await areaTitle(locale, {
          purpose: row.purpose,
          type: row.type,
          city: row.city ?? undefined,
          district: row.district ?? undefined,
        }),
        count: row.count,
      };
    }),
  );
}
