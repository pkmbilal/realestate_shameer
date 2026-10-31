"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError, type BrokerProfileInput, type City } from "@/lib/api/client";

const EMPTY: BrokerProfileInput = {
  name_ar: "",
  name_en: "",
  photo_url: "",
  fal_licence: "",
  whatsapp: "",
  city_ids: [],
};

type TextField = Exclude<keyof BrokerProfileInput, "city_ids">;

type State = "loading" | "needs_verification" | "ready";

export default function BrokerProfileForm({ cities }: { cities: City[] }) {
  const t = useTranslations("BrokerProfile");
  const locale = useLocale();
  const router = useRouter();
  const [state, setState] = useState<State>("loading");
  const [form, setForm] = useState<BrokerProfileInput>(EMPTY);
  const [agencyName, setAgencyName] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState<"saved" | "generic" | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const me = await api.me();
        if (!me.is_nafath_verified) return setState("needs_verification");
      } catch {
        return router.replace("/login");
      }
      try {
        const { agency, name_ar, name_en, photo_url, fal_licence, whatsapp, city_ids } =
          await api.brokers.me();
        setForm({ name_ar, name_en, photo_url, fal_licence, whatsapp, city_ids });
        if (agency) setAgencyName(locale === "ar" ? agency.name_ar : agency.name_en);
      } catch {
        // 404: no profile yet, start with an empty form.
      }
      setState("ready");
    }
    void load();
  }, [router, locale]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFieldErrors({});
    setMessage(null);
    try {
      const { whatsapp } = await api.brokers.saveMe(form);
      setForm((f) => ({ ...f, whatsapp }));
      setMessage("saved");
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) setFieldErrors(err.fieldErrors);
      else setMessage("generic");
    } finally {
      setBusy(false);
    }
  }

  function toggleCity(id: number) {
    setForm((f) => ({
      ...f,
      city_ids: f.city_ids.includes(id) ? f.city_ids.filter((c) => c !== id) : [...f.city_ids, id],
    }));
  }

  if (state === "loading") return <div className="h-40" aria-busy />;

  if (state === "needs_verification") {
    return (
      <div className="flex flex-col gap-4">
        <p className="rounded-md bg-amber-50 px-4 py-3 text-amber-800">{t("needsVerification")}</p>
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

  function textField(name: TextField, options: { dir?: "ltr" | "rtl"; type?: string } = {}) {
    const hasError = Boolean(fieldErrors[name]);
    return (
      <label className="flex flex-col gap-2">
        <span className="font-medium">{t(`fields.${name}`)}</span>
        <input
          type={options.type ?? "text"}
          dir={options.dir}
          value={form[name]}
          onChange={(e) => setForm((f) => ({ ...f, [name]: e.target.value }))}
          aria-invalid={hasError}
          className={`${inputClass} text-start ${hasError ? "border-red-500" : ""}`}
        />
        {hasError && <span className="text-sm text-red-700">{t(`errors.${name}`)}</span>}
      </label>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5" noValidate>
      {agencyName && (
        <p className="text-sm text-slate-600">{t("agency", { name: agencyName })}</p>
      )}
      {textField("name_ar", { dir: "rtl" })}
      {textField("name_en", { dir: "ltr" })}
      {textField("fal_licence", { dir: "ltr" })}
      {textField("whatsapp", { dir: "ltr", type: "tel" })}
      {textField("photo_url", { dir: "ltr", type: "url" })}

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 font-medium">{t("fields.city_ids")}</legend>
        <div className="grid grid-cols-2 gap-2">
          {cities.map((city) => (
            <label
              key={city.id}
              className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2"
            >
              <input
                type="checkbox"
                checked={form.city_ids.includes(city.id)}
                onChange={() => toggleCity(city.id)}
                className="size-4 accent-emerald-600"
              />
              {locale === "ar" ? city.name_ar : city.name_en}
            </label>
          ))}
        </div>
        {fieldErrors.city_ids && (
          <span className="text-sm text-red-700">{t("errors.city_ids")}</span>
        )}
      </fieldset>

      {message && (
        <p
          role={message === "saved" ? "status" : "alert"}
          className={`rounded-md px-3 py-2 text-sm ${
            message === "saved" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-700"
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
        {t("save")}
      </button>
    </form>
  );
}
