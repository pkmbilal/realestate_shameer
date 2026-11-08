"use client";

import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { useListingTitle } from "@/components/listings/title";
import PriceTag from "@/components/listings/PriceTag";
import { Link } from "@/i18n/navigation";
import {
  api,
  type CreditPrice,
  EDITABLE_STATUSES,
  type MyListing,
  type WalletAction,
  type WalletSummary,
} from "@/lib/api/client";
import { formatDate, formatNumber } from "@/lib/format";

import { type DashboardErrorKey, dashboardErrorKey } from "./errors";
import StatusChip from "./StatusChip";

/** The advertiser's listings with their status, dates, views, leads and actions. */
export default function MyListings() {
  const t = useTranslations("Dashboard");
  // undefined = loading, null = failed.
  const [listings, setListings] = useState<MyListing[] | null | undefined>(undefined);
  // The wallet is optional here: if it fails to load, the paid buttons just stay hidden.
  const [wallet, setWallet] = useState<WalletSummary | null>(null);

  function loadWallet() {
    api.wallet
      .get()
      .then(setWallet)
      .catch(() => setWallet(null));
  }

  useEffect(() => {
    api.myListings
      .list()
      .then(setListings)
      .catch(() => setListings(null));
    loadWallet();
  }, []);

  function replace(updated: MyListing) {
    setListings((all) => all?.map((l) => (l.reference === updated.reference ? updated : l)));
    loadWallet(); // the action may have spent or refunded credits
  }

  if (listings === undefined) return <div className="h-40" aria-busy />;
  if (listings === null) {
    return <p className="rounded-lg bg-red-50 p-4 text-red-700">{t("loadError")}</p>;
  }
  if (listings.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3 rounded-lg border border-dashed border-slate-300 p-6">
        <p className="text-slate-600">{t("empty")}</p>
        <Link
          href="/dashboard/listings/new"
          className="rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700"
        >
          {t("newListing")}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {wallet?.has_wallet && <BalanceBar balance={wallet.balance} />}
      <ul className="flex flex-col gap-3">
        {listings.map((listing) => (
          <li key={listing.reference}>
            <MyListingRow
              listing={listing}
              prices={wallet?.has_wallet ? wallet.prices : null}
              onChange={replace}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

function BalanceBar({ balance }: { balance: number }) {
  const t = useTranslations("Dashboard");
  const locale = useLocale();
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-emerald-50 px-4 py-2 text-sm text-emerald-900">
      <span className="font-medium">
        {t("balanceBar", { balance: formatNumber(balance, locale) })}
      </span>
      <Link href="/dashboard/wallet" className="font-medium underline underline-offset-2">
        {t("wallet")}
      </Link>
    </div>
  );
}

function priceOf(prices: CreditPrice[] | null, action: WalletAction): CreditPrice | undefined {
  return prices?.find((p) => p.action === action);
}

function MyListingRow({
  listing,
  prices,
  onChange,
}: {
  listing: MyListing;
  /** Current credit prices, or null when this advertiser has no wallet (owners). */
  prices: CreditPrice[] | null;
  onChange: (listing: MyListing) => void;
}) {
  const t = useTranslations("Dashboard");
  const locale = useLocale();
  const title = useListingTitle(listing);
  const [busy, setBusy] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);
  const [confirmPaid, setConfirmPaid] = useState<"refresh" | "feature" | null>(null);
  const [error, setError] = useState<DashboardErrorKey | null>(null);

  const editable = EDITABLE_STATUSES.includes(listing.status);
  const canSubmit = listing.status === "draft" && listing.missing_fields.length === 0;
  const canArchive = editable || listing.status === "expired";
  const cover = listing.photos[0];
  const featuredUntil =
    listing.status === "active" &&
    listing.featured_until &&
    new Date(listing.featured_until) > new Date()
      ? listing.featured_until
      : null;
  const postPrice = priceOf(prices, "post");
  const refreshPrice = priceOf(prices, "refresh");
  const featurePrice = priceOf(prices, "feature");
  const canPromote = listing.status === "active" && prices !== null;

  async function run(action: (reference: string) => Promise<MyListing>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await action(listing.reference));
    } catch (err) {
      setError(dashboardErrorKey(err));
    } finally {
      setBusy(false);
      setConfirmArchive(false);
      setConfirmPaid(null);
    }
  }

  const button =
    "rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium whitespace-nowrap hover:bg-slate-50 disabled:opacity-50";

  return (
    <article className="flex flex-col gap-3 rounded-xl border border-slate-200 p-3 sm:flex-row">
      <div className="aspect-[4/3] w-full shrink-0 overflow-hidden rounded-lg bg-slate-100 sm:w-40">
        {cover ? (
          <Image
            src={cover.card_url}
            alt=""
            width={640}
            height={480}
            unoptimized // already resized by imgproxy
            className="size-full object-cover"
          />
        ) : (
          <div className="flex size-full items-center justify-center text-sm text-slate-400">
            {t("noPhoto")}
          </div>
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <StatusChip status={listing.status} />
          {featuredUntil && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
              {t("featuredUntil")} {formatDate(featuredUntil, locale)}
            </span>
          )}
          <span className="text-xs text-slate-500" dir="ltr">
            {listing.reference}
          </span>
        </div>
        <h2 className="truncate font-semibold">{title}</h2>
        <PriceTag
          halalas={listing.price_halalas}
          rentPeriod={listing.rent_period}
          className="font-bold text-emerald-800"
        />

        <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-slate-600">
          <div>
            <dt className="inline">{t("licenceExpires")} </dt>
            <dd className="inline">{formatDate(listing.licence_expires_on, locale)}</dd>
          </div>
          {listing.post_expires_at && (
            <div>
              <dt className="inline">{t("postExpires")} </dt>
              <dd className="inline">{formatDate(listing.post_expires_at, locale)}</dd>
            </div>
          )}
          <div>{t("views", { count: listing.view_count })}</div>
          <div>{t("leads", { count: listing.lead_count })}</div>
        </dl>

        {listing.moderation_note &&
          (listing.status === "draft" || listing.status === "taken_down") && (
            <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {t("moderationNote", { note: listing.moderation_note })}
            </p>
          )}
        {listing.status === "draft" && listing.missing_fields.length > 0 && (
          <p className="text-sm text-slate-500">{t("incompleteHint")}</p>
        )}
        {canSubmit && postPrice && postPrice.credits > 0 && (
          <p className="text-sm text-slate-500">
            {t("submitCost", { credits: postPrice.credits })}
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-red-700">
            {t(`errors.${error}`)}
          </p>
        )}

        <div className="flex flex-wrap gap-2 pt-1">
          {editable && (
            <Link
              href={`/dashboard/listings/${listing.reference}`}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700"
            >
              {t("actions.edit")}
            </Link>
          )}
          {canSubmit && (
            <button
              type="button"
              disabled={busy}
              className={button}
              onClick={() => run(api.myListings.submit)}
            >
              {t("actions.submit")}
            </button>
          )}
          {listing.status === "active" && (
            <Link href={`/listings/${listing.reference}`} className={button}>
              {t("actions.view")}
            </Link>
          )}
          {canPromote &&
            (confirmPaid ? (
              <>
                <button
                  type="button"
                  disabled={busy}
                  className={`${button} border-emerald-600 text-emerald-800 hover:bg-emerald-50`}
                  onClick={() =>
                    run(confirmPaid === "refresh" ? api.myListings.refresh : api.myListings.feature)
                  }
                >
                  {confirmPaid === "refresh"
                    ? t("actions.confirmRefresh", { credits: refreshPrice?.credits ?? 0 })
                    : t("actions.confirmFeature", {
                        credits: featurePrice?.credits ?? 0,
                        days: featurePrice?.days ?? 0,
                      })}
                </button>
                <button type="button" className={button} onClick={() => setConfirmPaid(null)}>
                  {t("actions.cancel")}
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className={button}
                  onClick={() => {
                    setConfirmArchive(false);
                    setConfirmPaid("refresh");
                  }}
                >
                  {t("actions.refresh")}
                </button>
                <button
                  type="button"
                  className={button}
                  onClick={() => {
                    setConfirmArchive(false);
                    setConfirmPaid("feature");
                  }}
                >
                  {t("actions.feature")}
                </button>
              </>
            ))}
          {canArchive &&
            !confirmPaid &&
            (confirmArchive ? (
              <>
                <button
                  type="button"
                  disabled={busy}
                  className={`${button} border-red-300 text-red-700 hover:bg-red-50`}
                  onClick={() => run(api.myListings.archive)}
                >
                  {t("actions.confirmArchive")}
                </button>
                <button type="button" className={button} onClick={() => setConfirmArchive(false)}>
                  {t("actions.cancel")}
                </button>
              </>
            ) : (
              <button type="button" className={button} onClick={() => setConfirmArchive(true)}>
                {t("actions.archive")}
              </button>
            ))}
        </div>
      </div>
    </article>
  );
}
