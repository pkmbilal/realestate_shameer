/**
 * The sitemaps listed in /sitemap.xml:
 *   /sitemaps/pages.xml       home and search
 *   /sitemaps/areas.xml       area pages that have listings
 *   /sitemaps/listings-N.xml  active listings, 5,000 per file
 */
import { type Locale, routing } from "@/i18n/routing";
import { api } from "@/lib/api/client";
import { localizedAreaPath, rowToArea } from "@/lib/seo/areas";
import { type SitemapEntry, urlset } from "@/lib/seo/sitemap";

export const dynamic = "force-dynamic";

type Context = { params: Promise<{ file: string }> };

const perLocale = (pathFor: (locale: Locale) => string) =>
  Object.fromEntries(routing.locales.map((l) => [l, pathFor(l)])) as Record<Locale, string>;

async function entriesFor(file: string): Promise<SitemapEntry[] | null> {
  if (file === "pages.xml") {
    return [{ paths: perLocale((l) => `/${l}`) }, { paths: perLocale((l) => `/${l}/search`) }];
  }

  if (file === "areas.xml") {
    const rows = await api.seo.areas();
    return rows
      .filter((row) => row.count > 0)
      .map((row) => ({
        paths: perLocale((l) => localizedAreaPath(l, rowToArea(row))),
      }));
  }

  const match = /^listings-([1-9]\d*)\.xml$/.exec(file);
  if (match) {
    const chunk = await api.seo.sitemapListings(Number(match[1]));
    if (chunk.results.length === 0 && Number(match[1]) > 1) return null;
    return chunk.results.map((listing) => ({
      paths: perLocale((l) => `/${l}/listings/${listing.reference}`),
      lastmod: listing.updated_at,
    }));
  }
  return null;
}

export async function GET(_request: Request, { params }: Context) {
  const { file } = await params;
  let entries: SitemapEntry[] | null;
  try {
    entries = await entriesFor(file);
  } catch {
    return new Response("Sitemap temporarily unavailable", { status: 503 });
  }
  if (entries === null) return new Response("Not found", { status: 404 });
  return urlset(entries);
}
