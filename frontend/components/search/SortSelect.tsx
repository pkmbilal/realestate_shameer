"use client";

import { useTranslations } from "next-intl";

import { useRouter } from "@/i18n/navigation";
import { type SortKey, toQuery } from "@/lib/api/client";

const SORTS: SortKey[] = ["newest", "price_asc", "price_desc"];

/** Changing the sort goes back to page 1 and keeps the other filters. */
export default function SortSelect({ query }: { query: Record<string, unknown> }) {
  const t = useTranslations("Search");
  const router = useRouter();
  const current = (query.sort as SortKey | undefined) ?? "newest";

  return (
    <label className="flex items-center gap-2 text-sm text-slate-700">
      <span className="whitespace-nowrap">{t("sort")}</span>
      <select
        value={current}
        onChange={(e) => {
          const sort = e.target.value === "newest" ? undefined : e.target.value;
          router.push(`/search${toQuery({ ...query, sort, page: undefined })}`);
        }}
        className="rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm"
      >
        {SORTS.map((sort) => (
          <option key={sort} value={sort}>
            {t(`sortOptions.${sort}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
