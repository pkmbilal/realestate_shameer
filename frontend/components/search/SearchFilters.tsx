"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import {
  api,
  type City,
  type District,
  PROPERTY_TYPES,
  type PropertyType,
  type SearchParams,
  toQuery,
} from "@/lib/api/client";
import { localized } from "@/lib/format";
import type { SearchView } from "@/lib/search";

type Props = {
  params: SearchParams;
  cities: City[];
  view: SearchView;
};

type Form = {
  purpose: string;
  city: string;
  district: string;
  type: PropertyType[];
  price_min: string;
  price_max: string;
  beds_min: string;
  baths_min: string;
  area_min: string;
  area_max: string;
  completion: string;
  furnishing: string;
  rent_period: string;
};

function toForm(p: SearchParams): Form {
  const s = (v: string | number | undefined) => (v === undefined ? "" : String(v));
  return {
    purpose: s(p.purpose),
    city: s(p.city),
    district: s(p.district),
    type: p.type ?? [],
    price_min: s(p.price_min),
    price_max: s(p.price_max),
    beds_min: s(p.beds_min),
    baths_min: s(p.baths_min),
    area_min: s(p.area_min),
    area_max: s(p.area_max),
    completion: s(p.completion),
    furnishing: s(p.furnishing),
    rent_period: s(p.rent_period),
  };
}

const digitsOnly = (value: string) => value.replace(/\D/g, "").slice(0, 11);

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-emerald-600 focus:outline-none";
const labelClass = "flex flex-col gap-1 text-sm font-medium text-slate-700";

/** The search form. Submitting writes the filters to the URL; the page re-renders on the server. */
export default function SearchFilters({ params, cities, view }: Props) {
  const t = useTranslations("Search");
  const tp = useTranslations("Property");
  const locale = useLocale();
  const router = useRouter();
  const [form, setForm] = useState<Form>(() => toForm(params));
  const [districts, setDistricts] = useState<District[]>([]);
  const [open, setOpen] = useState(false);

  // Keep the form in step when the URL changes (back button, purpose tabs).
  const paramsKey = JSON.stringify(params);
  useEffect(() => {
    setForm(toForm(JSON.parse(paramsKey) as SearchParams));
  }, [paramsKey]);

  useEffect(() => {
    if (!form.city) {
      setDistricts([]);
      return;
    }
    let cancelled = false;
    api.locations
      .districts(form.city)
      .then((list) => !cancelled && setDistricts(list))
      .catch(() => !cancelled && setDistricts([]));
    return () => {
      cancelled = true;
    };
  }, [form.city]);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function toggleType(type: PropertyType) {
    set("type", form.type.includes(type) ? form.type.filter((x) => x !== type) : [...form.type, type]);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const query = {
      ...form,
      district: form.city ? form.district : "",
      rent_period: form.purpose === "rent" ? form.rent_period : "",
      sort: params.sort,
      view: view === "map" ? "map" : undefined,
    };
    setOpen(false);
    router.push(`/search${toQuery(query)}`);
  }

  function reset() {
    setForm(toForm({ purpose: params.purpose }));
    router.push(`/search${toQuery({ purpose: params.purpose, view: view === "map" ? "map" : undefined })}`);
  }

  const counts = ["1", "2", "3", "4", "5"];

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="flex gap-2">
        <label className="sr-only" htmlFor="filter-city">
          {t("city")}
        </label>
        <select
          id="filter-city"
          value={form.city}
          onChange={(e) => setForm((f) => ({ ...f, city: e.target.value, district: "" }))}
          className={inputClass}
        >
          <option value="">{t("anyCity")}</option>
          {cities.map((city) => (
            <option key={city.id} value={city.slug_en}>
              {localized(city.name_ar, city.name_en, locale)}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="more-filters"
          className="shrink-0 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 lg:hidden"
        >
          {t("filters")}
        </button>
        <button
          type="submit"
          className="shrink-0 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          {t("apply")}
        </button>
      </div>

      <div
        id="more-filters"
        className={`${open ? "grid" : "hidden"} grid-cols-2 gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-3 lg:grid lg:grid-cols-6`}
      >
        <label className={labelClass}>
          {t("district")}
          <select
            value={form.district}
            onChange={(e) => set("district", e.target.value)}
            disabled={!form.city}
            className={inputClass}
          >
            <option value="">{t("anyDistrict")}</option>
            {districts.map((d) => (
              <option key={d.id} value={d.slug_en}>
                {localized(d.name_ar, d.name_en, locale)}
              </option>
            ))}
          </select>
        </label>

        <label className={labelClass}>
          {t("anyPurpose")}
          <select value={form.purpose} onChange={(e) => set("purpose", e.target.value)} className={inputClass}>
            <option value="">{t("any")}</option>
            <option value="sale">{tp("purposeTitle.sale")}</option>
            <option value="rent">{tp("purposeTitle.rent")}</option>
          </select>
        </label>

        <fieldset className="col-span-2 flex flex-col gap-1 sm:col-span-3 lg:col-span-4">
          <legend className="mb-1 text-sm font-medium text-slate-700">{t("propertyType")}</legend>
          <div className="flex flex-wrap gap-2">
            {PROPERTY_TYPES.map((type) => {
              const on = form.type.includes(type);
              return (
                <button
                  key={type}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleType(type)}
                  className={`rounded-full border px-3 py-1 text-sm ${
                    on ? "border-emerald-600 bg-emerald-50 text-emerald-800" : "border-slate-300 hover:bg-slate-50"
                  }`}
                >
                  {tp(`type.${type}`)}
                </button>
              );
            })}
          </div>
        </fieldset>

        <fieldset className="col-span-2 flex flex-col gap-1">
          <legend className="mb-1 text-sm font-medium text-slate-700">{t("price")}</legend>
          <div className="flex gap-2">
            <input
              inputMode="numeric"
              dir="ltr"
              aria-label={`${t("price")} — ${t("min")}`}
              placeholder={t("min")}
              value={form.price_min}
              onChange={(e) => set("price_min", digitsOnly(e.target.value))}
              className={inputClass}
            />
            <input
              inputMode="numeric"
              dir="ltr"
              aria-label={`${t("price")} — ${t("max")}`}
              placeholder={t("max")}
              value={form.price_max}
              onChange={(e) => set("price_max", digitsOnly(e.target.value))}
              className={inputClass}
            />
          </div>
        </fieldset>

        <fieldset className="col-span-2 flex flex-col gap-1">
          <legend className="mb-1 text-sm font-medium text-slate-700">{t("area")}</legend>
          <div className="flex gap-2">
            <input
              inputMode="numeric"
              dir="ltr"
              aria-label={`${t("area")} — ${t("min")}`}
              placeholder={t("min")}
              value={form.area_min}
              onChange={(e) => set("area_min", digitsOnly(e.target.value))}
              className={inputClass}
            />
            <input
              inputMode="numeric"
              dir="ltr"
              aria-label={`${t("area")} — ${t("max")}`}
              placeholder={t("max")}
              value={form.area_max}
              onChange={(e) => set("area_max", digitsOnly(e.target.value))}
              className={inputClass}
            />
          </div>
        </fieldset>

        <label className={labelClass}>
          {t("beds")}
          <select value={form.beds_min} onChange={(e) => set("beds_min", e.target.value)} className={inputClass}>
            <option value="">{t("any")}</option>
            {counts.map((n) => (
              <option key={n} value={n}>
                {t("plus", { count: n })}
              </option>
            ))}
          </select>
        </label>

        <label className={labelClass}>
          {t("baths")}
          <select value={form.baths_min} onChange={(e) => set("baths_min", e.target.value)} className={inputClass}>
            <option value="">{t("any")}</option>
            {counts.slice(0, 4).map((n) => (
              <option key={n} value={n}>
                {t("plus", { count: n })}
              </option>
            ))}
          </select>
        </label>

        <label className={labelClass}>
          {t("completion")}
          <select value={form.completion} onChange={(e) => set("completion", e.target.value)} className={inputClass}>
            <option value="">{t("any")}</option>
            <option value="ready">{tp("completion.ready")}</option>
            <option value="off_plan">{tp("completion.off_plan")}</option>
          </select>
        </label>

        <label className={labelClass}>
          {t("furnishing")}
          <select value={form.furnishing} onChange={(e) => set("furnishing", e.target.value)} className={inputClass}>
            <option value="">{t("any")}</option>
            <option value="unfurnished">{tp("furnishing.unfurnished")}</option>
            <option value="semi_furnished">{tp("furnishing.semi_furnished")}</option>
            <option value="furnished">{tp("furnishing.furnished")}</option>
          </select>
        </label>

        {form.purpose === "rent" && (
          <label className={labelClass}>
            {t("rentPeriod")}
            <select value={form.rent_period} onChange={(e) => set("rent_period", e.target.value)} className={inputClass}>
              <option value="">{t("any")}</option>
              <option value="yearly">{tp("rentPeriodName.yearly")}</option>
              <option value="monthly">{tp("rentPeriodName.monthly")}</option>
            </select>
          </label>
        )}

        <div className="col-span-2 flex items-end gap-2 sm:col-span-3 lg:col-span-6 lg:justify-end">
          <button
            type="button"
            onClick={reset}
            className="rounded-md px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            {t("reset")}
          </button>
        </div>
      </div>
    </form>
  );
}
