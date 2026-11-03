import { useLocale, useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import type { City } from "@/lib/api/client";

/** "Browse by city" cards, each linking to that city's search results. */
export default function CityList({ cities }: { cities: City[] }) {
  const t = useTranslations("Home");
  const locale = useLocale();

  if (cities.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-lg font-bold">{t("browseByCity")}</h2>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {cities.map((city) => (
          <li key={city.id}>
            <Link
              href={`/search?city=${city.slug_en}`}
              className="block rounded-lg border border-slate-200 px-4 py-3 font-medium text-slate-800 hover:border-emerald-600 hover:bg-emerald-50"
            >
              {locale === "ar" ? city.name_ar : city.name_en}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
