"use client";

import { useLocale, useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { api, type LeadChannel } from "@/lib/api/client";

import EnquiryForm from "./EnquiryForm";
import { errorKey, type LeadErrorKey } from "./errors";

type Props = { reference: string };

/**
 * WhatsApp, call and enquiry buttons for a listing.
 *
 * Each click is logged by the API first, which then returns the contact link. On phones
 * the buttons sit in a bar fixed to the bottom of the screen; on desktop they sit in the
 * advertiser card.
 */
export default function ContactPanel({ reference }: Props) {
  const t = useTranslations("Leads");
  const locale = useLocale();
  const [busy, setBusy] = useState<LeadChannel | null>(null);
  const [error, setError] = useState<LeadErrorKey | null>(null);
  const [phoneNumber, setPhoneNumber] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const formRef = useRef<HTMLDivElement>(null);

  async function contact(channel: "whatsapp" | "call") {
    setBusy(channel);
    setError(null);
    try {
      const lead = await api.leads.create({ listing: reference, channel, locale });
      const url = channel === "whatsapp" ? lead.whatsapp_url : lead.tel_url;
      if (!url) throw new Error("missing contact link");
      // Desktop browsers often can't place calls, so the number is shown as well.
      if (channel === "call") setPhoneNumber(url.replace(/^tel:/, ""));
      window.location.href = url;
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(null);
    }
  }

  function openForm() {
    setFormOpen(true);
    // Wait for the form to render, then bring it into view (it may be off-screen on phones).
    requestAnimationFrame(() =>
      formRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }),
    );
  }

  const button =
    "flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-3 text-sm font-bold disabled:opacity-60";

  return (
    <div className="flex flex-col gap-3">
      <div className="fixed inset-x-0 bottom-0 z-20 flex gap-2 border-t border-slate-200 bg-white p-3 shadow-[0_-2px_8px_rgba(0,0,0,0.06)] lg:static lg:flex-col lg:border-0 lg:p-0 lg:shadow-none">
        <button
          type="button"
          onClick={() => void contact("whatsapp")}
          disabled={busy !== null}
          className={`${button} bg-emerald-600 text-white hover:bg-emerald-700`}
        >
          <WhatsAppIcon />
          {t("whatsapp")}
        </button>
        <button
          type="button"
          onClick={() => void contact("call")}
          disabled={busy !== null}
          className={`${button} border border-emerald-600 text-emerald-700 hover:bg-emerald-50`}
        >
          <PhoneIcon />
          {t("call")}
        </button>
        <button
          type="button"
          onClick={openForm}
          aria-expanded={formOpen}
          className={`${button} border border-slate-300 text-slate-700 hover:bg-slate-50`}
        >
          <MailIcon />
          {t("enquire")}
        </button>
      </div>

      {phoneNumber && (
        <p className="text-sm text-slate-600">
          {t("callNumber")}{" "}
          <a href={`tel:${phoneNumber}`} dir="ltr" className="font-mono font-bold text-emerald-700">
            {phoneNumber}
          </a>
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {t(`errors.${error}`)}
        </p>
      )}
      {formOpen && (
        <div ref={formRef}>
          <EnquiryForm reference={reference} />
        </div>
      )}
    </div>
  );
}

function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="size-5 fill-current">
      <path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.9c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.8 11.9 11.9 0 0 0 4.6 4c1.7.7 2.4.8 3.2.7.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.3-.2-.5-.3z" />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="size-5 fill-none stroke-current" strokeWidth={2}>
      <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className="size-5 fill-none stroke-current" strokeWidth={2}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3 7 9 6 9-6" />
    </svg>
  );
}
