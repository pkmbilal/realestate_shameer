import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { api, type AreaCount } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";
import { areaPath, rowToArea } from "@/lib/seo/areas";
import { areaTitle } from "@/lib/seo/titles";

const LIMIT = 12;

async function loadCounts(): Promise<AreaCount[]> {
  try {
    return await api.seo.areas();
  } catch {
    return [];
  }
}

/** "Popular searches": the city-level area pages with the most listings (internal links). */
export default async function PopularAreas({ locale }: { locale: Locale }) {
  const rows = (await loadCounts())
    .filter((row) => row.city !== null && row.district === null)
    .sort((a, b) => b.count - a.count)
    .slice(0, LIMIT);
  if (rows.length === 0) return null;

  const t = await getTranslations({ locale, namespace: "Area" });
  const links = await Promise.all(
    rows.map(async (row) => ({
      href: areaPath(locale, rowToArea(row)),
      label: await areaTitle(locale, {
        purpose: row.purpose,
        type: row.type,
        city: row.city ?? undefined,
      }),
      count: row.count,
    })),
  );

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-bold">{t("popular")}</h2>
      <ul className="grid gap-2 sm:grid-cols-2">
        {links.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="text-emerald-700 hover:underline">
              {link.label}
            </Link>{" "}
            <span className="text-sm text-slate-500">({formatNumber(link.count, locale)})</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
