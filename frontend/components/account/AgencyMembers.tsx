"use client";

import { useLocale, useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { api, ApiError, type AgencyMember } from "@/lib/api/client";

const ADD_ERRORS = [
  "invalid_phone",
  "broker_not_found",
  "broker_in_other_agency",
] as const;
type AddError = (typeof ADD_ERRORS)[number] | "generic";

/** The agency admin's list of member brokers, with add-by-phone and remove. */
export default function AgencyMembers() {
  const t = useTranslations("AgencyProfile.members");
  const locale = useLocale();
  const [members, setMembers] = useState<AgencyMember[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [phone, setPhone] = useState("");
  const [addError, setAddError] = useState<AddError | null>(null);
  const [added, setAdded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [removeFailed, setRemoveFailed] = useState(false);

  useEffect(() => {
    api.brokers
      .members()
      .then(setMembers)
      .catch(() => setLoadFailed(true));
  }, []);

  async function onAdd(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setAddError(null);
    setAdded(false);
    try {
      const member = await api.brokers.addMember(phone);
      setMembers((list) => [
        ...(list ?? []).filter((m) => m.id !== member.id),
        member,
      ]);
      setPhone("");
      setAdded(true);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : undefined;
      setAddError(ADD_ERRORS.find((c) => c === code) ?? "generic");
    } finally {
      setBusy(false);
    }
  }

  async function onRemove(id: number) {
    setBusy(true);
    setRemoveFailed(false);
    try {
      await api.brokers.removeMember(id);
      setMembers((list) => (list ?? []).filter((m) => m.id !== id));
      setConfirmId(null);
    } catch {
      setRemoveFailed(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-5 border-t border-slate-200 pt-8">
      <div className="flex flex-col gap-1">
        <h2 className="text-xl font-bold">{t("title")}</h2>
        <p className="text-sm text-slate-600">{t("intro")}</p>
      </div>

      {loadFailed && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {t("loadFailed")}
        </p>
      )}
      {members === null && !loadFailed && <div className="h-16" aria-busy />}
      {members?.length === 0 && (
        <p className="text-sm text-slate-500">{t("empty")}</p>
      )}

      {members && members.length > 0 && (
        <ul className="flex flex-col gap-3">
          {members.map((member) => {
            const name = locale === "ar" ? member.name_ar : member.name_en;
            return (
              <li
                key={member.id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 p-3"
              >
                {member.photo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element -- external photo link, not served through imgproxy yet
                  <img
                    src={member.photo_url}
                    alt=""
                    className="size-12 rounded-full object-cover"
                  />
                ) : (
                  <span
                    aria-hidden
                    className="flex size-12 items-center justify-center rounded-full bg-slate-100 font-bold text-slate-500"
                  >
                    {name.charAt(0)}
                  </span>
                )}
                <div className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate font-medium">{name}</span>
                  <span className="text-sm text-slate-600">
                    {t("fal")} <span dir="ltr">{member.fal_licence}</span>
                  </span>
                  <span dir="ltr" className="self-start text-sm text-slate-600">
                    {member.masked_whatsapp}
                  </span>
                </div>
                {confirmId === member.id ? (
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onRemove(member.id)}
                      className="rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      {t("confirmRemove")}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmId(null)}
                      className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50"
                    >
                      {t("cancel")}
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmId(member.id)}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50"
                  >
                    {t("remove")}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {removeFailed && (
        <p
          role="alert"
          className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          {t("removeFailed")}
        </p>
      )}

      <form onSubmit={onAdd} className="flex flex-col gap-3" noValidate>
        <label className="flex flex-col gap-2">
          <span className="font-medium">{t("addLabel")}</span>
          <input
            type="tel"
            dir="ltr"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="05XXXXXXXX"
            aria-invalid={Boolean(addError)}
            className={`w-full rounded-lg border px-4 py-3 text-start focus:border-emerald-600 focus:outline-none ${
              addError ? "border-red-500" : "border-slate-300"
            }`}
          />
          <span className="text-sm text-slate-500">{t("addHint")}</span>
        </label>
        {addError && (
          <p
            role="alert"
            className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            {t(`errors.${addError}`)}
          </p>
        )}
        {added && (
          <p
            role="status"
            className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
          >
            {t("added")}
          </p>
        )}
        <button
          type="submit"
          disabled={busy || phone.trim() === ""}
          className="rounded-lg border border-emerald-600 px-4 py-3 font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
        >
          {t("add")}
        </button>
      </form>
    </section>
  );
}
