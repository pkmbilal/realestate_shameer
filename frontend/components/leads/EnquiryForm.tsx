"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";

import { api, ApiError } from "@/lib/api/client";

import { errorKey, type LeadErrorKey } from "./errors";

type Props = { reference: string };

/** Name, phone and message sent to the advertiser. The phone is only shared with them. */
export default function EnquiryForm({ reference }: Props) {
  const t = useTranslations("Leads");
  const locale = useLocale();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<LeadErrorKey | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setSending(true);
    setError(null);
    setFieldErrors({});
    try {
      await api.leads.create({ listing: reference, channel: "form", locale, name, phone, message });
      setSent(true);
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fieldErrors).length) {
        setFieldErrors(
          Object.fromEntries(Object.entries(err.fieldErrors).map(([k, v]) => [k, v[0] ?? ""])),
        );
      } else {
        setError(errorKey(err));
      }
    } finally {
      setSending(false);
    }
  }

  if (sent) {
    return (
      <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">
        {t("form.sent")}
      </p>
    );
  }

  const input =
    "w-full rounded-lg border border-slate-300 px-3 py-2 text-base focus:border-emerald-600 focus:outline-none";
  const fieldError = (field: string) =>
    fieldErrors[field] && (
      <span className="text-xs text-red-600">
        {t(fieldErrors[field] === "required" ? "errors.required" : "errors.invalidPhone")}
      </span>
    );

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4"
    >
      <h3 className="font-bold">{t("form.title")}</h3>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">{t("form.name")}</span>
        <input
          autoComplete="name"
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={input}
        />
        {fieldError("name")}
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">{t("form.phone")}</span>
        <input
          type="tel"
          inputMode="tel"
          autoComplete="tel"
          dir="ltr"
          placeholder="05XXXXXXXX"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          className={`${input} text-start`}
        />
        {fieldError("phone")}
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">{t("form.message")}</span>
        <textarea
          rows={3}
          maxLength={1000}
          placeholder={t("form.messagePlaceholder")}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          className={input}
        />
      </label>
      <p className="text-xs text-slate-500">{t("form.privacy")}</p>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {t(`errors.${error}`)}
        </p>
      )}
      <button
        type="submit"
        disabled={sending}
        className="rounded-lg bg-emerald-600 px-4 py-2 font-bold text-white hover:bg-emerald-700 disabled:opacity-60"
      >
        {sending ? t("form.sending") : t("form.send")}
      </button>
    </form>
  );
}
