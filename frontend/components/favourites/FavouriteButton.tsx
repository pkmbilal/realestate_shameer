"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";

import { useFavourites } from "./FavouritesProvider";

type Props = {
  reference: string;
  /** "icon" sits on a photo; "button" shows text next to the heart. */
  variant?: "icon" | "button";
};

/** Heart toggle. Visitors who are not logged in are sent to the login page first. */
export default function FavouriteButton({ reference, variant = "icon" }: Props) {
  const t = useTranslations("Favourites");
  const favourites = useFavourites();
  const [failed, setFailed] = useState(false);
  if (!favourites) return null;

  const isSaved = favourites.saved?.has(reference) ?? false;
  const label = isSaved ? t("saved") : t("save");

  async function onClick(event: React.MouseEvent) {
    event.preventDefault(); // the button may sit inside a card link
    event.stopPropagation();
    setFailed(false);
    try {
      await favourites?.toggle(reference);
    } catch {
      setFailed(true);
    }
  }

  const heart = (
    <svg
      viewBox="0 0 24 24"
      aria-hidden
      className={`size-5 ${isSaved ? "fill-rose-500 stroke-rose-500" : "fill-none stroke-current"}`}
      strokeWidth={2}
    >
      <path d="M12 21s-7.5-4.6-9.5-9.2C1.2 8.6 3.2 5 6.6 5c2 0 3.4 1.1 4.4 2.5C12 6.1 13.4 5 15.4 5c3.4 0 5.4 3.6 4.1 6.8C19.5 16.4 12 21 12 21z" />
    </svg>
  );

  if (variant === "button") {
    return (
      <div className="flex flex-col gap-1">
        <button
          type="button"
          onClick={onClick}
          aria-pressed={isSaved}
          disabled={favourites.saved === undefined}
          className="flex items-center gap-2 rounded-md border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-50 disabled:opacity-50"
        >
          {heart}
          {label}
        </button>
        {failed && <p className="text-xs text-red-600">{t("error")}</p>}
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={isSaved}
      aria-label={label}
      title={failed ? t("error") : label}
      disabled={favourites.saved === undefined}
      className="flex size-9 items-center justify-center rounded-full bg-white/90 text-slate-700 shadow hover:bg-white disabled:opacity-50"
    >
      {heart}
    </button>
  );
}
