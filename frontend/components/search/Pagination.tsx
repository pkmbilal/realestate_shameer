import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { toQuery } from "@/lib/api/client";

type Props = {
  page: number;
  pages: number;
  /** The current URL query (without page) so filters are kept. */
  query: Record<string, unknown>;
  basePath: string;
};

/** Previous / next links. Plain links, so search engines can follow them too. */
export default function Pagination({ page, pages, query, basePath }: Props) {
  const t = useTranslations("Search");
  if (pages <= 1) return null;

  const href = (p: number) => `${basePath}${toQuery({ ...query, page: p > 1 ? p : undefined })}`;
  const linkClass = "rounded-md border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50";

  return (
    <nav className="flex items-center justify-between gap-3 py-4" aria-label={t("pageOf", { page, pages })}>
      {page > 1 ? (
        <Link href={href(page - 1)} rel="prev" className={linkClass}>
          {t("previous")}
        </Link>
      ) : (
        <span />
      )}
      <span className="text-sm text-slate-600">{t("pageOf", { page, pages })}</span>
      {page < pages ? (
        <Link href={href(page + 1)} rel="next" className={linkClass}>
          {t("next")}
        </Link>
      ) : (
        <span />
      )}
    </nav>
  );
}
