"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link } from "@/i18n/navigation";
import { api, type TopUp } from "@/lib/api/client";
import { formatNumber } from "@/lib/format";

// Ask again every 2 seconds, about a minute in all: the gateway, our server and the
// invoice task may each take a moment.
const POLL_MS = 2000;
const MAX_TRIES = 30;

/** Shown when the browser comes back from the payment page: paid, failed or still pending. */
export default function TopUpResult({ paymentId }: { paymentId: number }) {
  const t = useTranslations("Dashboard.TopUp.Result");
  const locale = useLocale();
  // undefined = first check running, null = not found.
  const [payment, setPayment] = useState<TopUp | null | undefined>(undefined);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;

    async function check() {
      tries += 1;
      try {
        const result = await api.topUps.get(paymentId);
        if (cancelled) return;
        setPayment(result);
        // Keep asking while it is pending, or while the paid invoice is being issued.
        const waiting =
          result.status === "pending" || (result.status === "paid" && !result.invoice_id);
        if (waiting && tries < MAX_TRIES) timer = setTimeout(check, POLL_MS);
        else setDone(true);
      } catch {
        if (!cancelled) setPayment(null);
      }
    }

    check();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [paymentId]);

  if (payment === undefined) {
    return (
      <p className="rounded-xl bg-slate-50 p-5 text-slate-700" aria-busy>
        {t("checking")}
      </p>
    );
  }
  if (payment === null) {
    return <p className="rounded-xl bg-red-50 p-5 text-red-700">{t("notFound")}</p>;
  }

  const walletLink = (
    <Link
      href="/dashboard/wallet"
      className="rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700"
    >
      {t("toWallet")}
    </Link>
  );

  if (payment.status === "paid") {
    return (
      <section className="flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-5">
        <h2 className="text-xl font-bold text-emerald-900">{t("paidTitle")}</h2>
        <p className="text-emerald-900">
          {t("paidBody", {
            credits: formatNumber(payment.credits, locale),
            balance: formatNumber(payment.balance, locale),
          })}
        </p>
        {payment.invoice_id ? (
          <a
            href={api.invoices.pdfUrl(payment.invoice_id)}
            className="self-start font-medium text-emerald-800 underline underline-offset-2"
          >
            {t("invoiceReady")}
          </a>
        ) : (
          <p className="text-sm text-emerald-800">{t("invoicePending")}</p>
        )}
        <div className="flex">{walletLink}</div>
      </section>
    );
  }

  if (payment.status === "pending" && !done) {
    return (
      <p className="rounded-xl bg-slate-50 p-5 text-slate-700" aria-busy>
        {t("checking")}
      </p>
    );
  }

  if (payment.status === "pending") {
    return (
      <section className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 p-5">
        <h2 className="text-xl font-bold text-amber-900">{t("pendingTitle")}</h2>
        <p className="text-amber-900">{t("pendingBody")}</p>
        <div className="flex">{walletLink}</div>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-3 rounded-xl border border-red-200 bg-red-50 p-5">
      <h2 className="text-xl font-bold text-red-900">{t("failedTitle")}</h2>
      <p className="text-red-900">{t("failedBody")}</p>
      <div className="flex flex-wrap gap-3">
        <Link
          href="/dashboard/wallet/top-up"
          className="rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700"
        >
          {t("tryAgain")}
        </Link>
        <Link
          href="/dashboard/wallet"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-medium hover:bg-slate-50"
        >
          {t("toWallet")}
        </Link>
      </div>
    </section>
  );
}
