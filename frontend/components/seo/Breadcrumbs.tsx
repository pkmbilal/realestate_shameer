import { getTranslations } from "next-intl/server";

import { Link } from "@/i18n/navigation";
import type { Locale } from "@/i18n/routing";
import { absoluteUrl, jsonLdHtml } from "@/lib/seo/meta";

export type Crumb = {
  label: string;
  /** Path without the locale prefix; omit for the current page. */
  href?: string;
};

type Props = { locale: Locale; items: Crumb[] };

/** Visible breadcrumb trail plus matching BreadcrumbList JSON-LD for search engines. */
export default async function Breadcrumbs({ locale, items }: Props) {
  const t = await getTranslations({ locale, namespace: "Area" });
  const trail: Crumb[] = [{ label: t("home"), href: "/" }, ...items];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: trail.map((crumb, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: crumb.label,
      item: crumb.href ? absoluteUrl(`/${locale}${crumb.href === "/" ? "" : crumb.href}`) : undefined,
    })),
  };

  return (
    <nav aria-label={t("breadcrumb")} className="text-sm text-slate-600">
      <script type="application/ld+json" dangerouslySetInnerHTML={jsonLdHtml(jsonLd)} />
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {trail.map((crumb, index) => (
          <li key={index} className="flex items-center gap-2">
            {index > 0 && (
              <span aria-hidden className="text-slate-400">
                /
              </span>
            )}
            {crumb.href ? (
              <Link href={crumb.href} className="font-medium text-emerald-700 hover:underline">
                {crumb.label}
              </Link>
            ) : (
              <span aria-current="page">{crumb.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
