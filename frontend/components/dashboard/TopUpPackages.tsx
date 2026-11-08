"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { api, ApiError, type TopUpPackage } from "@/lib/api/client";
import { formatNumber, formatSarExact, localized } from "@/lib/format";

const KNOWN_ERRORS = ["no_wallet", "package_not_found", "gateway_unavailable"] as const;
type KnownError = (typeof KNOWN_ERRORS)[number];

function isKnown(code: string | undefined): code is KnownError {
  return KNOWN_ERRORS.includes(code as KnownError);
}

/** Credit packages; buying one sends the browser to the payment gateway's checkout page. */
export default function TopUpPackages() {
  const t = useTranslations("Dashboard.TopUp");
  const tw = useTranslations("Dashboard.Wallet");
  const locale = useLocale();
  // undefined = loading, null = failed.
  const [packages, setPackages] = useState<TopUpPackage[] | null | undefined>(undefined);
  const [buying, setBuying] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.topUps
      .packages()
      .then(setPackages)
      .catch(() => setPackages(null));
  }, []);

  async function buy(pack: TopUpPackage) {
    setBuying(pack.id);
    setError(null);
    try {
      const { checkout_url } = await api.topUps.start(pack.id, locale);
      window.location.assign(checkout_url);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : undefined;
      if (err instanceof ApiError && err.status === 429) setError(t("errors.throttled"));
      else setError(t(`errors.${isKnown(code) ? code : "generic"}`));
      setBuying(null);
    }
  }

  if (packages === undefined) return <div className="h-40" aria-busy />;
  if (packages === null) {
    return <p className="rounded-lg bg-red-50 p-4 text-red-700">{t("loadError")}</p>;
  }
  if (packages.length === 0) {
    return <p className="rounded-lg bg-slate-50 p-4 text-slate-700">{t("noPackages")}</p>;
  }

  return (
    <div className="flex flex-col gap-4">
      {error && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-red-700">
          {error}
        </p>
      )}
      <ul className="grid gap-4 sm:grid-cols-3">
        {packages.map((pack) => (
          <li
            key={pack.id}
            className="flex flex-col gap-3 rounded-xl border border-slate-200 p-5 shadow-sm"
          >
            <h2 className="font-semibold text-slate-700">
              {localized(pack.name_ar, pack.name_en, locale)}
            </h2>
            <p className="text-2xl font-bold text-emerald-800">
              {tw("credits", { count: pack.credits, value: formatNumber(pack.credits, locale) })}
            </p>
            <div className="flex flex-col">
              <span className="text-lg font-semibold">
                {formatSarExact(pack.price_halalas, locale)}
              </span>
              <span className="text-xs text-slate-500">{t("vatIncluded")}</span>
            </div>
            <button
              type="button"
              onClick={() => buy(pack)}
              disabled={buying !== null}
              className="mt-auto rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {buying === pack.id ? t("redirecting") : t("buy")}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
