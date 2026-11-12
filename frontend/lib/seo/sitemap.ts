/** XML helpers for the sitemap route handlers (app/sitemap.xml and app/sitemaps/[file]). */
import { type Locale, routing } from "@/i18n/routing";

import { absoluteUrl } from "./meta";

export type SitemapEntry = {
  /** Path (with locale prefix) for each locale; the first locale's path is the <loc>. */
  paths: Record<Locale, string>;
  lastmod?: string;
};

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const HEADERS = {
  "Content-Type": "application/xml; charset=utf-8",
  // CDNs and crawlers may reuse a sitemap for an hour.
  "Cache-Control": "public, max-age=3600",
};

/**
 * One <url> per locale, each listing every language version as an hreflang alternate
 * (what Google asks for when language versions have different URLs).
 */
export function urlset(entries: SitemapEntry[]): Response {
  const urls = entries.flatMap((entry) =>
    routing.locales.map((locale) => {
      const alternates = routing.locales
        .map(
          (l) =>
            `<xhtml:link rel="alternate" hreflang="${l}" href="${escapeXml(absoluteUrl(entry.paths[l]))}"/>`,
        )
        .join("");
      const lastmod = entry.lastmod ? `<lastmod>${escapeXml(entry.lastmod)}</lastmod>` : "";
      return `<url><loc>${escapeXml(absoluteUrl(entry.paths[locale]))}</loc>${lastmod}${alternates}</url>`;
    }),
  );
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n` +
    urls.join("\n") +
    `\n</urlset>\n`;
  return new Response(xml, { headers: HEADERS });
}

export function sitemapIndex(locations: string[]): Response {
  const items = locations
    .map((path) => `<sitemap><loc>${escapeXml(absoluteUrl(path))}</loc></sitemap>`)
    .join("\n");
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${items}\n</sitemapindex>\n`;
  return new Response(xml, { headers: HEADERS });
}
