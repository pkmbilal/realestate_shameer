"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError, type AgencyInput } from "@/lib/api/client";

import AgencyMembers from "./AgencyMembers";

const EMPTY: AgencyInput = {
  name_ar: "",
  name_en: "",
  logo_url: "",
  cr_number: "",
  fal_licence: "",
};

type State = "loading" | "needs_verification" | "ready";

/**
 * Create or edit the agency the logged-in user runs. Saving it the first time makes them
 * the agency admin; after that they can add and remove member brokers.
 */
export default function AgencyProfileForm() {
  const t = useTranslations("AgencyProfile");
  const router = useRouter();
  const [state, setState] = useState<State>("loading");
  const [form, setForm] = useState<AgencyInput>(EMPTY);
  const [exists, setExists] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState<
    "saved" | "created" | "generic" | null
  >(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const me = await api.me();
        if (!me.is_nafath_verified) return setState("needs_verification");
      } catch {
        return router.replace(
          `/login?next=${encodeURIComponent("/account/agency")}`,
        );
      }
      try {
        const { name_ar, name_en, logo_url, cr_number, fal_licence } =
          await api.brokers.agency();
        setForm({ name_ar, name_en, logo_url, cr_number, fal_licence });
        setExists(true);
      } catch {
        // 404: no agency yet, start with an empty form.
      }
      setState("ready");
    }
    void load();
  }, [router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFieldErrors({});
    setMessage(null);
    try {
      await api.brokers.saveAgency(form);
      setMessage(exists ? "saved" : "created");
      setExists(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 400)
        setFieldErrors(err.fieldErrors);
      else setMessage("generic");
    } finally {
      setBusy(false);
    }
  }

  if (state === "loading") return <div className="h-40" aria-busy />;

  if (state === "needs_verification") {
    return (
      <div className="flex flex-col gap-4">
        <p className="rounded-md bg-amber-50 px-4 py-3 text-amber-800">
          {t("needsVerification")}
        </p>
        <Link
          href="/account/verify"
          className="rounded-lg bg-emerald-600 px-4 py-3 text-center font-medium text-white hover:bg-emerald-700"
        >
          {t("verifyNow")}
        </Link>
      </div>
    );
  }

  const inputClass =
    "w-full rounded-lg border border-slate-300 px-4 py-3 focus:border-emerald-600 focus:outline-none";

  function textField(
    name: keyof AgencyInput,
    options: { dir?: "ltr" | "rtl"; type?: string; inputMode?: "numeric" } = {},
  ) {
    const hasError = Boolean(fieldErrors[name]);
    return (
      <label className="flex flex-col gap-2">
        <span className="font-medium">{t(`fields.${name}`)}</span>
        <input
          type={options.type ?? "text"}
          dir={options.dir}
          inputMode={options.inputMode}
          value={form[name]}
          onChange={(e) => setForm((f) => ({ ...f, [name]: e.target.value }))}
          aria-invalid={hasError}
          className={`${inputClass} text-start ${hasError ? "border-red-500" : ""}`}
        />
        {hasError && (
          <span className="text-sm text-red-700">{t(`errors.${name}`)}</span>
        )}
      </label>
    );
  }

  return (
    <div className="flex flex-col gap-10">
      {!exists && (
        <p className="rounded-md bg-slate-50 px-4 py-3 text-sm text-slate-700">
          {t("createIntro")}
        </p>
      )}
      <form onSubmit={onSubmit} className="flex flex-col gap-5" noValidate>
        {form.logo_url.startsWith("https://") && (
          // eslint-disable-next-line @next/next/no-img-element -- external logo link, not served through imgproxy yet
          <img
            src={form.logo_url}
            alt={t("logoAlt")}
            className="size-20 rounded-lg border border-slate-200 object-contain"
          />
        )}
        {textField("name_ar", { dir: "rtl" })}
        {textField("name_en", { dir: "ltr" })}
        {textField("cr_number", { dir: "ltr", inputMode: "numeric" })}
        {textField("fal_licence", { dir: "ltr", inputMode: "numeric" })}
        {textField("logo_url", { dir: "ltr", type: "url" })}

        {message && (
          <p
            role={message === "generic" ? "alert" : "status"}
            className={`rounded-md px-3 py-2 text-sm ${
              message === "generic"
                ? "bg-red-50 text-red-700"
                : "bg-emerald-50 text-emerald-800"
            }`}
          >
            {t(message)}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="rounded-lg bg-emerald-600 px-4 py-3 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          {exists ? t("save") : t("create")}
        </button>
      </form>

      {exists && <AgencyMembers />}
    </div>
  );
}
