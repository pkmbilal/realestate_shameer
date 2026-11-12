/** Sitemap index: points to one sitemap per content type (pages, areas, listings). */
import { api } from "@/lib/api/client";
import { sitemapIndex } from "@/lib/seo/sitemap";

// Built per request (cached by crawlers for an hour) so it never depends on the API at build time.
export const dynamic = "force-dynamic";

export async function GET() {
  let listingChunks = 1;
  try {
    const first = await api.seo.sitemapListings(1);
    listingChunks = Math.max(1, Math.ceil(first.count / first.chunk_size));
  } catch {
    return new Response("Sitemap temporarily unavailable", { status: 503 });
  }
  const files = [
    "/sitemaps/pages.xml",
    "/sitemaps/areas.xml",
    ...Array.from({ length: listingChunks }, (_, i) => `/sitemaps/listings-${i + 1}.xml`),
  ];
  return sitemapIndex(files);
}
