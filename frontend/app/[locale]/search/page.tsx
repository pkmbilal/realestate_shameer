import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import FavouritesProvider from "@/components/favourites/FavouritesProvider";
import ListingCard from "@/components/listings/ListingCard";
import Pagination from "@/components/search/Pagination";
import SearchFilters from "@/components/search/SearchFilters";
import SearchMapPanel from "@/components/search/SearchMap";
import SortSelect from "@/components/search/SortSelect";
import SiteHeader from "@/components/SiteHeader";
import { Link } from "@/i18n/navigation";
import { type Locale, routing } from "@/i18n/routing";
import {
  api,
  type City,
  type ListingCard as Card,
  type Page,
  type SearchParams,
  toQuery,
} from "@/lib/api/client";
import { localized } from "@/lib/format";
import { parseSearchParams, parseView, type RawSearchParams } from "@/lib/search";
import { type Area, localizedAreaPath } from "@/lib/seo/areas";
import { languageAlternates, robotsFor } from "@/lib/seo/meta";

const PAGE_SIZE = 20; // matches ListingPagination on the API

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<RawSearchParams>;
};

async function loadCities(): Promise<City[]> {
  try {
    return await api.locations.cities();
  } catch {
    return [];
  }
}

async function loadResults(params: SearchParams): Promise<Page<Card> | null> {
  try {
    return await api.listings.search(params);
  } catch {
    return null;
  }
}

/** Only plain "purpose / city / type" pages are worth indexing; filtered views are not. */
function isIndexable(params: SearchParams): boolean {
  const allowed = ["purpose", "city", "type", "sort"];
  const extra = Object.entries(params).filter(
    ([key, value]) => !allowed.includes(key) && value !== undefined,
  );
  return extra.length === 0 && (params.type?.length ?? 0) <= 1;
}

/** The area page that shows exactly these results (purpose + one type, maybe a city). */
async function matchingArea(params: SearchParams): Promise<Area | null> {
  const type = params.type?.length === 1 ? params.type[0] : undefined;
  if (!params.purpose || !type) return null;
  if (!params.city) return { purpose: params.purpose, type };
  const city = (await loadCities()).find((c) => c.slug_en === params.city);
  return city ? { purpose: params.purpose, type, city } : null;
}

async function pageTitle(locale: Locale, params: SearchParams, cities: City[]): Promise<string> {
  const t = await getTranslations({ locale, namespace: "Search" });
  const tp = await getTranslations({ locale, namespace: "Property" });
  const city = cities.find((c) => c.slug_en === params.city);
  const place = city ? localized(city.name_ar, city.name_en, locale) : t("everywhere");
  if (!params.purpose && !params.type) return t("metaTitleAll", { place });
  const onlyType = params.type?.length === 1 ? params.type[0] : undefined;
  const what = onlyType ? tp(`typePlural.${onlyType}`) : t("properties");
  const purpose = params.purpose ? tp(`purpose.${params.purpose}`) : "";
  return t("metaTitle", { what, purpose, place }).replace(/\s+/g, " ");
}

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const search = parseSearchParams(await searchParams);
  const title = await pageTitle(locale, search, await loadCities());
  const indexable = isIndexable(search);
  const area = indexable ? await matchingArea(search) : null;
  if (area) {
    // "Apartments for rent in Dammam" has its own area page; point search engines there.
    return {
      title,
      alternates: {
        canonical: localizedAreaPath(locale, area),
        languages: languageAlternates((l) => localizedAreaPath(l, area)),
      },
      robots: robotsFor(true),
    };
  }
  const query = toQuery({ purpose: search.purpose, city: search.city, type: search.type });
  return {
    title,
    alternates: {
      canonical: `/${locale}/search${query}`,
      languages: languageAlternates((l) => `/${l}/search${query}`),
    },
    robots: robotsFor(indexable),
  };
}

export default async function SearchPage({ params, searchParams }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);

  const raw = await searchParams;
  const search = parseSearchParams(raw);
  const view = parseView(raw);
  const [cities, results] = await Promise.all([loadCities(), loadResults(search)]);
  const t = await getTranslations("Search");
  const tn = await getTranslations("Nav");

  const city = cities.find((c) => c.slug_en === search.city) ?? null;
  const page = search.page ?? 1;
  const pages = results ? Math.max(1, Math.ceil(results.count / PAGE_SIZE)) : 1;
  const query = { ...search, page: undefined, view: view === "map" ? "map" : undefined };
  const filtersOnly: SearchParams = { ...search, page: undefined, sort: undefined };
  const title = await pageTitle(locale, search, cities);

  const tab = (purpose: "sale" | "rent" | undefined, label: string) => {
    const active = search.purpose === purpose;
    return (
      <Link
        href={`/search${toQuery({ ...query, purpose, rent_period: undefined, sort: search.sort })}`}
        aria-current={active ? "page" : undefined}
        className={`rounded-full px-4 py-1.5 text-sm font-medium ${
          active ? "bg-emerald-600 text-white" : "border border-slate-300 hover:bg-slate-50"
        }`}
      >
        {label}
      </Link>
    );
  };

  const viewLink = (target: "list" | "map", label: string) => (
    <Link
      href={`/search${toQuery({ ...query, view: target === "map" ? "map" : undefined, page: search.page })}`}
      aria-current={view === target ? "page" : undefined}
      className={`px-3 py-1.5 text-sm font-medium ${
        view === target ? "bg-slate-900 text-white" : "bg-white hover:bg-slate-50"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <FavouritesProvider>
      <main className="mx-auto flex min-h-dvh max-w-7xl flex-col gap-4 px-4 py-6 sm:px-6">
        <SiteHeader />

        <div className="flex flex-col gap-3">
          <h1 className="text-2xl font-bold">{title}</h1>
          <nav className="flex gap-2" aria-label={t("anyPurpose")}>
            {tab(undefined, t("any"))}
            {tab("sale", tn("buy"))}
            {tab("rent", tn("rent"))}
          </nav>
          <SearchFilters params={search} cities={cities} view={view} />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-medium whitespace-nowrap text-slate-700" aria-live="polite">
            {results ? t("results", { count: results.count }) : ""}
          </p>
          <div className="flex items-center gap-3">
            <SortSelect query={query} />
            <div className="flex overflow-hidden rounded-md border border-slate-300 lg:hidden">
              {viewLink("list", t("viewList"))}
              {viewLink("map", t("viewMap"))}
            </div>
          </div>
        </div>

        <div className="grid flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <section className={view === "map" ? "hidden lg:block" : ""}>
            {results === null ? (
              <p className="rounded-lg bg-red-50 p-4 text-red-700">{t("loadError")}</p>
            ) : results.results.length === 0 ? (
              <p className="rounded-lg bg-slate-50 p-4 text-slate-600">{t("noResults")}</p>
            ) : (
              <>
                <ul className="grid gap-4 sm:grid-cols-2">
                  {results.results.map((listing) => (
                    <li key={listing.reference}>
                      <ListingCard listing={listing} />
                    </li>
                  ))}
                </ul>
                <Pagination page={page} pages={pages} query={query} basePath="/search" />
              </>
            )}
          </section>

          <aside className={view === "map" ? "" : "hidden lg:block"}>
            <SearchMapPanel
              mobileVisible={view === "map"}
              params={filtersOnly}
              center={city?.center ?? null}
              className="h-[70dvh] lg:sticky lg:top-4 lg:h-[calc(100dvh-2rem)]"
            />
          </aside>
        </div>
      </main>
    </FavouritesProvider>
  );
}
