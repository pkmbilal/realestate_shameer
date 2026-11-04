"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api/client";

import { type DashboardErrorKey, dashboardErrorKey } from "./errors";

/**
 * Step 1 of a new listing: the REGA ad licence number. REGA supplies the property type,
 * purpose, area and location, so the advertiser never types those (CLAUDE.md §2 rule 2).
 */
export default function StartListingForm() {
  const t = useTranslations("Dashboard");
  const router = useRouter();
  const [licence, setLicence] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<DashboardErrorKey | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const listing = await api.myListings.start(licence.trim());
      router.push(`/dashboard/listings/${listing.reference}`);
    } catch (err) {
      setError(dashboardErrorKey(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <label className="flex flex-col gap-2">
        <span className="font-medium">{t("start.licenceLabel")}</span>
        <input
          dir="ltr"
          inputMode="numeric"
          autoComplete="off"
          value={licence}
          onChange={(e) => setLicence(e.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby="licence-hint"
          className={`w-full rounded-lg border px-4 py-3 text-start font-mono focus:border-emerald-600 focus:outline-none ${
            error ? "border-red-500" : "border-slate-300"
          }`}
        />
        <span id="licence-hint" className="text-sm text-slate-500">
          {t("start.hint")}
        </span>
      </label>
      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {t(`errors.${error}`)}
        </p>
      )}
      <button
        type="submit"
        disabled={busy || licence.trim() === ""}
        className="rounded-lg bg-emerald-600 px-4 py-3 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
      >
        {busy ? t("start.checking") : t("start.submit")}
      </button>
    </form>
  );
}
