import { getTranslations } from "next-intl/server";

import type { Locale } from "@/i18n/routing";
import type { PropertyType, Purpose } from "@/lib/api/client";

type Named = { name_ar: string; name_en: string };

export type TitledArea = { purpose: Purpose; type: PropertyType; city?: Named; district?: Named };

/** Translated parts of an area title: "Apartments" / "for rent" / "Al Shulah, Dammam". */
export async function areaTitleParts(locale: Locale, area: TitledArea) {
  const tp = await getTranslations({ locale, namespace: "Property" });
  const ts = await getTranslations({ locale, namespace: "Search" });
  const ta = await getTranslations({ locale, namespace: "Area" });
  const name = (p: Named) => (locale === "ar" ? p.name_ar : p.name_en);

  let place = ts("everywhere");
  if (area.city && area.district) {
    place = ta("districtInCity", { district: name(area.district), city: name(area.city) });
  } else if (area.city) {
    place = name(area.city);
  }
  return { what: tp(`typePlural.${area.type}`), purpose: tp(`purpose.${area.purpose}`), place };
}

/** "Apartments for rent in Al Shulah, Dammam" / "شقق للإيجار في الشعلة، الدمام" */
export async function areaTitle(locale: Locale, area: TitledArea): Promise<string> {
  const ta = await getTranslations({ locale, namespace: "Area" });
  return ta("inPlace", await areaTitleParts(locale, area));
}
