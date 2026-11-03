import { useLocale, useTranslations } from "next-intl";

import type { RentPeriod } from "@/lib/api/client";
import { formatSar } from "@/lib/format";

type Props = {
  halalas: number | null;
  rentPeriod?: RentPeriod | "";
  className?: string;
};

/** "SAR 850,000" or "SAR 60,000 / year". */
export default function PriceTag({ halalas, rentPeriod, className }: Props) {
  const t = useTranslations("Property");
  const locale = useLocale();

  if (halalas === null) {
    return <span className={className}>{t("priceOnRequest")}</span>;
  }
  return (
    <span className={className}>
      <bdi>{formatSar(halalas, locale)}</bdi>
      {rentPeriod ? (
        <span className="ms-1 text-sm font-normal text-slate-500">{t(`rentPeriod.${rentPeriod}`)}</span>
      ) : null}
    </span>
  );
}
