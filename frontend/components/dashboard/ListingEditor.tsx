"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import ListingLocationMap from "@/components/listings/ListingLocationMap";
import RegaBadge from "@/components/listings/RegaBadge";
import { Link, useRouter } from "@/i18n/navigation";
import {
  type Amenity,
  api,
  ApiError,
  type Completion,
  EDITABLE_STATUSES,
  type Furnishing,
  type MyListing,
  type MyListingInput,
  type RentPeriod,
} from "@/lib/api/client";
import { formatNumber, localized } from "@/lib/format";

import { type DashboardErrorKey, dashboardErrorKey, isMissingField } from "./errors";
import PhotoManager from "./PhotoManager";
import StatusChip from "./StatusChip";

/** What the inputs hold. Numbers stay as text until saving so typing is never fought. */
type Form = {
  price: string;
  rent_period: RentPeriod | "";
  bedrooms: string;
  bathrooms: string;
  furnishing: Furnishing | "";
  completion: Completion;
  title_ar: string;
  title_en: string;
  description_ar: string;
  description_en: string;
  amenity_ids: number[];
};

const FURNISHING: Furnishing[] = ["unfurnished", "semi_furnished", "furnished"];
const COMPLETION: Completion[] = ["ready", "off_plan"];
const RENT_PERIODS: RentPeriod[] = ["yearly", "monthly"];

function toForm(l: MyListing): Form {
  return {
    // Prices are whole riyals in the form and integer halalas in the API.
    price: l.price_halalas === null ? "" : String(Math.round(l.price_halalas / 100)),
    rent_period: l.rent_period,
    bedrooms: l.bedrooms === null ? "" : String(l.bedrooms),
    bathrooms: l.bathrooms === null ? "" : String(l.bathrooms),
    furnishing: l.furnishing,
    completion: l.completion,
    title_ar: l.title_ar,
    title_en: l.title_en,
    description_ar: l.description_ar,
    description_en: l.description_en,
    amenity_ids: l.amenity_ids,
  };
}

/** "١٢٣" or "1,234" → 1234; "" → null; anything else → NaN. */
function parseWhole(text: string): number | null {
  const digits = text
    .replace(/[٠-٩]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[,\s٬]/g, "");
  if (digits === "") return null;
  return /^\d+$/.test(digits) ? Number(digits) : Number.NaN;
}

function toInput(form: Form): { input: Partial<MyListingInput>; invalid: string[] } {
  const price = parseWhole(form.price);
  const bedrooms = parseWhole(form.bedrooms);
  const bathrooms = parseWhole(form.bathrooms);
  const invalid = Object.entries({ price_halalas: price, bedrooms, bathrooms })
    .filter(([, v]) => Number.isNaN(v))
    .map(([k]) => k);
  return {
    invalid,
    input: {
      price_halalas: price === null ? null : price * 100,
      rent_period: form.rent_period,
      bedrooms,
      bathrooms,
      furnishing: form.furnishing,
      completion: form.completion,
      title_ar: form.title_ar.trim(),
      title_en: form.title_en.trim(),
      description_ar: form.description_ar.trim(),
      description_en: form.description_en.trim(),
      amenity_ids: form.amenity_ids,
    },
  };
}

type Message = { kind: "ok" } | { kind: "error"; key: DashboardErrorKey } | null;

/** Edit one of my listings: REGA facts read-only, my fields editable, photos, submit. */
export default function ListingEditor({ reference }: { reference: string }) {
  const t = useTranslations("Dashboard");
  const tp = useTranslations("Property");
  const locale = useLocale();
  const router = useRouter();
  // undefined = loading, null = not found / failed.
  const [listing, setListing] = useState<MyListing | null | undefined>(undefined);
  const [amenities, setAmenities] = useState<Amenity[]>([]);
  const [form, setForm] = useState<Form | null>(null);
  const [fieldErrors, setFieldErrors] = useState<string[]>([]);
  const [message, setMessage] = useState<Message>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.myListings
      .get(reference)
      .then((l) => {
        setListing(l);
        setForm(toForm(l));
      })
      .catch(() => setListing(null));
    api.listings
      .amenities()
      .then(setAmenities)
      .catch(() => setAmenities([]));
  }, [reference]);

  if (listing === undefined || (listing && !form)) return <div className="h-40" aria-busy />;
  if (listing === null || form === null) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="rounded-lg bg-red-50 p-4 text-red-700">{t("editor.notFound")}</p>
        <Link href="/dashboard" className="font-medium text-emerald-700 hover:underline">
          {t("backToList")}
        </Link>
      </div>
    );
  }

  const editable = EDITABLE_STATUSES.includes(listing.status);
  const isRent = listing.purpose === "rent";

  function set<K extends keyof Form>(name: K, value: Form[K]) {
    setForm((f) => (f ? { ...f, [name]: value } : f));
  }

  /** Save the form. Returns the saved listing, or null if it could not be saved. */
  async function save(): Promise<MyListing | null> {
    if (!form || !listing) return null;
    const { input, invalid } = toInput(form);
    setFieldErrors(invalid);
    if (invalid.length > 0) {
      setMessage({ kind: "error", key: "invalid" });
      return null;
    }
    try {
      const saved = await api.myListings.update(listing.reference, input);
      setListing(saved);
      setForm(toForm(saved));
      return saved;
    } catch (err) {
      if (err instanceof ApiError) setFieldErrors(Object.keys(err.fieldErrors));
      setMessage({ kind: "error", key: dashboardErrorKey(err) });
      return null;
    }
  }

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    const saved = await save();
    if (saved) setMessage({ kind: "ok" });
    setBusy(false);
  }

  async function onSubmitForReview() {
    setBusy(true);
    setMessage(null);
    const saved = await save();
    if (saved) {
      try {
        await api.myListings.submit(saved.reference);
        router.push("/dashboard");
        return;
      } catch (err) {
        setMessage({ kind: "error", key: dashboardErrorKey(err) });
        // Refresh so the "still needed" list is current.
        api.myListings.get(saved.reference).then(setListing, () => undefined);
      }
    }
    setBusy(false);
  }

  const place = [listing.district, listing.city]
    .filter((p) => p !== null)
    .map((p) => localized(p.name_ar, p.name_en, locale))
    .join(locale === "ar" ? "، " : ", ");

  const inputClass = (name: string) =>
    `w-full rounded-lg border px-4 py-3 text-start focus:border-emerald-600 focus:outline-none disabled:bg-slate-50 ${
      fieldErrors.includes(name) ? "border-red-500" : "border-slate-300"
    }`;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center gap-3">
        <StatusChip status={listing.status} />
        <span className="text-sm text-slate-500" dir="ltr">
          {listing.reference}
        </span>
        <Link href="/dashboard" className="ms-auto text-sm font-medium text-emerald-700 hover:underline">
          {t("backToList")}
        </Link>
      </div>

      {listing.moderation_note && listing.status === "draft" && (
        <p className="rounded-md bg-amber-50 px-4 py-3 text-amber-900">
          {t("moderationNote", { note: listing.moderation_note })}
        </p>
      )}
      {!editable && <p className="rounded-md bg-slate-100 px-4 py-3">{t("editor.notEditable")}</p>}
      {listing.status === "active" && (
        <p className="rounded-md bg-amber-50 px-4 py-3 text-amber-900">{t("editor.activeWarning")}</p>
      )}
      {listing.status === "pending_review" && (
        <p className="rounded-md bg-sky-50 px-4 py-3 text-sky-900">{t("editor.pendingNote")}</p>
      )}

      {/* REGA facts: read-only, supplied by the licence. */}
      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{t("editor.regaTitle")}</h2>
        <p className="text-sm text-slate-500">{t("editor.regaHint")}</p>
        <RegaBadge licenceNumber={listing.licence_number} expiresOn={listing.licence_expires_on} />
        <dl className="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-4 text-sm sm:grid-cols-4">
          <Fact label={t("editor.facts.purpose")}>{tp(`purposeTitle.${listing.purpose}`)}</Fact>
          <Fact label={t("editor.facts.type")}>{tp(`type.${listing.property_type}`)}</Fact>
          <Fact label={t("editor.facts.area")}>
            {tp("area", { area: formatNumber(listing.area_m2, locale) })}
          </Fact>
          <Fact label={t("editor.facts.place")}>{place}</Fact>
        </dl>
        <ListingLocationMap lat={listing.latitude} lng={listing.longitude} />
      </section>

      <PhotoManager listing={listing} editable={editable} onListing={setListing} />

      <form onSubmit={onSave} className="flex flex-col gap-5" noValidate>
        <h2 className="text-lg font-semibold">{t("editor.detailsTitle")}</h2>
        <fieldset disabled={!editable || busy} className="flex flex-col gap-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label={t("editor.fields.price")} error={fieldErrors.includes("price_halalas")}>
              <input
                dir="ltr"
                inputMode="numeric"
                value={form.price}
                onChange={(e) => set("price", e.target.value)}
                className={inputClass("price_halalas")}
              />
            </Field>
            {isRent && (
              <Field label={t("editor.fields.rent_period")} error={fieldErrors.includes("rent_period")}>
                <select
                  value={form.rent_period}
                  onChange={(e) => set("rent_period", e.target.value as RentPeriod | "")}
                  className={inputClass("rent_period")}
                >
                  <option value="">{t("editor.choose")}</option>
                  {RENT_PERIODS.map((p) => (
                    <option key={p} value={p}>
                      {tp(`rentPeriodName.${p}`)}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field label={t("editor.fields.bedrooms")} error={fieldErrors.includes("bedrooms")}>
              <input
                dir="ltr"
                inputMode="numeric"
                value={form.bedrooms}
                onChange={(e) => set("bedrooms", e.target.value)}
                className={inputClass("bedrooms")}
              />
            </Field>
            <Field label={t("editor.fields.bathrooms")} error={fieldErrors.includes("bathrooms")}>
              <input
                dir="ltr"
                inputMode="numeric"
                value={form.bathrooms}
                onChange={(e) => set("bathrooms", e.target.value)}
                className={inputClass("bathrooms")}
              />
            </Field>
            <Field label={t("editor.fields.furnishing")} error={fieldErrors.includes("furnishing")}>
              <select
                value={form.furnishing}
                onChange={(e) => set("furnishing", e.target.value as Furnishing | "")}
                className={inputClass("furnishing")}
              >
                <option value="">{t("editor.notSpecified")}</option>
                {FURNISHING.map((f) => (
                  <option key={f} value={f}>
                    {tp(`furnishing.${f}`)}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={t("editor.fields.completion")} error={fieldErrors.includes("completion")}>
              <select
                value={form.completion}
                onChange={(e) => set("completion", e.target.value as Completion)}
                className={inputClass("completion")}
              >
                {COMPLETION.map((c) => (
                  <option key={c} value={c}>
                    {tp(`completion.${c}`)}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label={t("editor.fields.title_ar")} error={fieldErrors.includes("title_ar")}>
            <input
              dir="rtl"
              maxLength={200}
              value={form.title_ar}
              onChange={(e) => set("title_ar", e.target.value)}
              className={inputClass("title_ar")}
            />
          </Field>
          <Field label={t("editor.fields.title_en")} error={fieldErrors.includes("title_en")}>
            <input
              dir="ltr"
              maxLength={200}
              value={form.title_en}
              onChange={(e) => set("title_en", e.target.value)}
              className={inputClass("title_en")}
            />
          </Field>
          <Field label={t("editor.fields.description_ar")} error={fieldErrors.includes("description_ar")}>
            <textarea
              dir="rtl"
              rows={5}
              value={form.description_ar}
              onChange={(e) => set("description_ar", e.target.value)}
              className={inputClass("description_ar")}
            />
          </Field>
          <Field label={t("editor.fields.description_en")} error={fieldErrors.includes("description_en")}>
            <textarea
              dir="ltr"
              rows={5}
              value={form.description_en}
              onChange={(e) => set("description_en", e.target.value)}
              className={inputClass("description_en")}
            />
          </Field>

          {amenities.length > 0 && (
            <div role="group" aria-labelledby="amenities-label" className="flex flex-col gap-2">
              <span id="amenities-label" className="font-medium">
                {t("editor.fields.amenities")}
              </span>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {amenities.map((a) => (
                  <label
                    key={a.id}
                    className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={form.amenity_ids.includes(a.id)}
                      onChange={() =>
                        set(
                          "amenity_ids",
                          form.amenity_ids.includes(a.id)
                            ? form.amenity_ids.filter((id) => id !== a.id)
                            : [...form.amenity_ids, a.id],
                        )
                      }
                      className="size-4 accent-emerald-600"
                    />
                    {localized(a.name_ar, a.name_en, locale)}
                  </label>
                ))}
              </div>
            </div>
          )}
        </fieldset>

        {listing.status === "draft" && listing.missing_fields.length > 0 && (
          <div className="rounded-md bg-slate-50 px-4 py-3 text-sm">
            <p className="font-medium">{t("editor.missingTitle")}</p>
            <ul className="mt-1 list-disc ps-5 text-slate-600">
              {listing.missing_fields.filter(isMissingField).map((f) => (
                <li key={f}>{t(`editor.missing.${f}`)}</li>
              ))}
            </ul>
          </div>
        )}

        {message && (
          <p
            role={message.kind === "ok" ? "status" : "alert"}
            className={`rounded-md px-3 py-2 text-sm ${
              message.kind === "ok" ? "bg-emerald-50 text-emerald-800" : "bg-red-50 text-red-700"
            }`}
          >
            {message.kind === "ok" ? t("editor.saved") : t(`errors.${message.key}`)}
          </p>
        )}

        {editable && (
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="submit"
              disabled={busy}
              className="rounded-lg border border-emerald-600 px-4 py-3 font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
            >
              {t("editor.save")}
            </button>
            {listing.status === "draft" && (
              <button
                type="button"
                disabled={busy}
                onClick={onSubmitForReview}
                className="rounded-lg bg-emerald-600 px-4 py-3 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
              >
                {t("editor.submit")}
              </button>
            )}
          </div>
        )}
      </form>
    </div>
  );
}

function Field({ label, error, children }: { label: string; error: boolean; children: ReactNode }) {
  const t = useTranslations("Dashboard.editor");
  return (
    <label className="flex flex-col gap-2">
      <span className="font-medium">{label}</span>
      {children}
      {error && <span className="text-sm text-red-700">{t("checkField")}</span>}
    </label>
  );
}

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-slate-500">{label}</dt>
      <dd className="font-medium">{children}</dd>
    </div>
  );
}
