"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link } from "@/i18n/navigation";
import {
  api,
  type CreditTransaction,
  type Invoice,
  type Page,
  type WalletSummary,
} from "@/lib/api/client";
import { formatDate, formatNumber, formatSarExact } from "@/lib/format";

/** The advertiser's credit balance, current prices and wallet history. */
export default function WalletOverview() {
  const t = useTranslations("Dashboard.Wallet");
  // undefined = loading, null = failed.
  const [wallet, setWallet] = useState<WalletSummary | null | undefined>(undefined);

  useEffect(() => {
    api.wallet
      .get()
      .then(setWallet)
      .catch(() => setWallet(null));
  }, []);

  if (wallet === undefined) return <div className="h-40" aria-busy />;
  if (wallet === null) {
    return <p className="rounded-lg bg-red-50 p-4 text-red-700">{t("loadError")}</p>;
  }
  if (!wallet.has_wallet) {
    return <p className="rounded-lg bg-slate-50 p-4 text-slate-700">{t("noWallet")}</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <BalanceCard balance={wallet.balance} />
      <Prices prices={wallet.prices} />
      <History />
      <Invoices />
    </div>
  );
}

function BalanceCard({ balance }: { balance: number }) {
  const t = useTranslations("Dashboard.Wallet");
  const locale = useLocale();
  return (
    <section className="flex flex-col gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-col gap-1">
        <h2 className="text-sm font-medium text-emerald-900">{t("balance")}</h2>
        <p className="text-3xl font-bold text-emerald-900">
          {t("credits", { count: balance, value: formatNumber(balance, locale) })}
        </p>
      </div>
      <Link
        href="/dashboard/wallet/top-up"
        className="self-start rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 sm:self-auto"
      >
        {t("topUp")}
      </Link>
    </section>
  );
}

function Prices({ prices }: { prices: WalletSummary["prices"] }) {
  const t = useTranslations("Dashboard.Wallet");
  const locale = useLocale();
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">{t("pricesTitle")}</h2>
      <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200">
        {prices.map((price) => (
          <li key={price.action} className="flex items-center justify-between gap-3 px-4 py-3">
            <span>{t(`price.${price.action}`, { days: price.days })}</span>
            <span className="font-semibold whitespace-nowrap">
              {price.credits === 0
                ? t("free")
                : t("credits", {
                    count: price.credits,
                    value: formatNumber(price.credits, locale),
                  })}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function History() {
  const t = useTranslations("Dashboard.Wallet");
  const locale = useLocale();
  const [page, setPage] = useState<Page<CreditTransaction> | null | undefined>(undefined);
  const [rows, setRows] = useState<CreditTransaction[]>([]);
  const [pageNumber, setPageNumber] = useState(1);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.wallet
      .transactions(pageNumber)
      .then((result) => {
        setPage(result);
        setRows((previous) => (pageNumber === 1 ? result.results : [...previous, ...result.results]));
      })
      .catch(() => setPage(null))
      .finally(() => setLoading(false));
  }, [pageNumber]);

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">{t("historyTitle")}</h2>
      {page === undefined && <div className="h-24" aria-busy />}
      {page === null && <p className="text-red-700">{t("loadError")}</p>}
      {page && rows.length === 0 && <p className="text-slate-600">{t("historyEmpty")}</p>}
      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="px-3 py-2 text-start font-medium">{t("columns.date")}</th>
                <th className="px-3 py-2 text-start font-medium">{t("columns.entry")}</th>
                <th className="px-3 py-2 text-end font-medium">{t("columns.amount")}</th>
                <th className="px-3 py-2 text-end font-medium">{t("columns.balance")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {formatDate(row.created_at, locale)}
                  </td>
                  <td className="px-3 py-2">
                    <div className="font-medium">
                      {t(`kind.${row.kind}`)}
                      {row.action && ` · ${t(`action.${row.action}`)}`}
                    </div>
                    {(row.listing || row.note) && (
                      <div className="text-xs text-slate-500">
                        {row.listing && <span dir="ltr">{row.listing}</span>}
                        {row.listing && row.note && " · "}
                        {row.note}
                      </div>
                    )}
                  </td>
                  <td
                    className={`px-3 py-2 text-end font-semibold whitespace-nowrap ${
                      row.amount > 0 ? "text-emerald-700" : "text-red-700"
                    }`}
                    dir="ltr"
                  >
                    {row.amount > 0 ? "+" : ""}
                    {formatNumber(row.amount, locale)}
                  </td>
                  <td className="px-3 py-2 text-end whitespace-nowrap" dir="ltr">
                    {formatNumber(row.balance_after, locale)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {page?.next && (
        <button
          type="button"
          disabled={loading}
          onClick={() => setPageNumber((n) => n + 1)}
          className="self-start rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
        >
          {t("loadMore")}
        </button>
      )}
    </section>
  );
}

function Invoices() {
  const t = useTranslations("Dashboard.Wallet");
  const locale = useLocale();
  // undefined = loading, null = failed.
  const [invoices, setInvoices] = useState<Invoice[] | null | undefined>(undefined);

  useEffect(() => {
    api.invoices
      .list()
      .then((page) => setInvoices(page.results))
      .catch(() => setInvoices(null));
  }, []);

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">{t("invoicesTitle")}</h2>
      {invoices === undefined && <div className="h-16" aria-busy />}
      {invoices === null && <p className="text-red-700">{t("loadError")}</p>}
      {invoices?.length === 0 && <p className="text-slate-600">{t("invoicesEmpty")}</p>}
      {invoices && invoices.length > 0 && (
        <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200">
          {invoices.map((invoice) => (
            <li
              key={invoice.id}
              className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 text-sm"
            >
              <div className="flex flex-col">
                <span className="font-medium" dir="ltr">
                  {invoice.number}
                </span>
                <span className="text-slate-500">
                  {formatDate(invoice.issued_at, locale)} ·{" "}
                  {t("credits", {
                    count: invoice.credits,
                    value: formatNumber(invoice.credits, locale),
                  })}
                </span>
              </div>
              <div className="flex items-center gap-4">
                <span className="font-semibold whitespace-nowrap">
                  {formatSarExact(invoice.total_halalas, locale)}
                </span>
                <a
                  href={api.invoices.pdfUrl(invoice.id)}
                  className="font-medium text-emerald-700 underline-offset-2 hover:underline"
                >
                  {t("download")}
                </a>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
