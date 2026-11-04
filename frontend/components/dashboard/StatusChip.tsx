import { useTranslations } from "next-intl";

import type { ListingStatus } from "@/lib/api/client";

const COLOURS: Record<ListingStatus, string> = {
  draft: "bg-slate-100 text-slate-700",
  pending_review: "bg-amber-100 text-amber-800",
  active: "bg-emerald-100 text-emerald-800",
  expired: "bg-orange-100 text-orange-800",
  taken_down: "bg-red-100 text-red-800",
  archived: "bg-slate-100 text-slate-500",
};

export default function StatusChip({ status }: { status: ListingStatus }) {
  const t = useTranslations("Dashboard.status");
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${COLOURS[status]}`}
    >
      {t(status)}
    </span>
  );
}
