import { useLocale, useTranslations } from "next-intl";

import { formatDate } from "@/lib/format";

type Props = { licenceNumber: string; expiresOn: string };

/** Required on every listing page (REGA advertising rules): the ad licence number. */
export default function RegaBadge({ licenceNumber, expiresOn }: Props) {
  const t = useTranslations("Listing");
  const locale = useLocale();

  return (
    <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
      <svg viewBox="0 0 24 24" aria-hidden className="mt-0.5 size-6 shrink-0 fill-emerald-700">
        <path d="M12 2 4 5v6c0 5 3.4 9.7 8 11 4.6-1.3 8-6 8-11V5l-8-3zm-1.2 14.2-3.5-3.5 1.4-1.4 2.1 2.1 4.9-4.9 1.4 1.4-6.3 6.3z" />
      </svg>
      <div className="flex min-w-0 flex-col gap-0.5 text-sm">
        <span className="font-bold text-emerald-900">{t("regaBadge")}</span>
        <span className="text-emerald-900">
          {t("regaLicence")}{" "}
          <bdi dir="ltr" className="font-mono font-bold">
            {licenceNumber}
          </bdi>
        </span>
        <span className="text-emerald-800">
          {t("regaExpires", { date: formatDate(expiresOn, locale) })}
        </span>
      </div>
    </div>
  );
}
