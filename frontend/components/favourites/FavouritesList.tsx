"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import ListingCard from "@/components/listings/ListingCard";
import { Link } from "@/i18n/navigation";
import { api, ApiError, type ListingCard as Card } from "@/lib/api/client";

/**
 * The signed-in user's saved listings. Loaded in the browser because it needs the login
 * cookie. Un-saving a listing keeps it on screen until the page is reloaded.
 */
export default function FavouritesList() {
  const t = useTranslations("Favourites");
  // undefined = loading, null = not logged in.
  const [listings, setListings] = useState<Card[] | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    api.favourites
      .list()
      .then((page) => setListings(page.results))
      .catch((error) => {
        if (error instanceof ApiError && error.status === 401) setListings(null);
        else setFailed(true);
      });
  }, []);

  if (failed) return <p className="rounded-lg bg-red-50 p-4 text-red-700">{t("error")}</p>;
  if (listings === undefined) return <div className="h-40" aria-busy />;

  if (listings === null) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-slate-600">{t("loginNeeded")}</p>
        <Link
          href={`/login?next=${encodeURIComponent("/account/favourites")}`}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          {t("login")}
        </Link>
      </div>
    );
  }

  if (listings.length === 0) {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-slate-600">{t("empty")}</p>
        <Link href="/search" className="font-medium text-emerald-700 hover:underline">
          {t("browse")}
        </Link>
      </div>
    );
  }

  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {listings.map((listing) => (
        <li key={listing.reference}>
          <ListingCard listing={listing} />
        </li>
      ))}
    </ul>
  );
}
