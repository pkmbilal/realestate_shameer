"use client";

import { useLocale, useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";

/** Links to the same page in the other language. */
export default function LocaleSwitcher() {
  const t = useTranslations("LocaleSwitcher");
  const locale = useLocale();
  const pathname = usePathname();
  const otherLocale = locale === "ar" ? "en" : "ar";

  return (
    <Link
      href={pathname}
      locale={otherLocale}
      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium whitespace-nowrap hover:bg-slate-50"
    >
      {t("label")}
    </Link>
  );
}
