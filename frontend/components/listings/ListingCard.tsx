import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";

import FavouriteButton from "@/components/favourites/FavouriteButton";
import { Link } from "@/i18n/navigation";
import type { ListingCard as Card } from "@/lib/api/client";
import { formatNumber, localized } from "@/lib/format";

import PriceTag from "./PriceTag";
import { useListingTitle } from "./title";

/** One search result. The whole card links to the listing page. */
export default function ListingCard({ listing }: { listing: Card }) {
  const t = useTranslations("Property");
  const locale = useLocale();
  const title = useListingTitle(listing);
  const place = [listing.district, listing.city]
    .filter((p) => p !== null)
    .map((p) => localized(p.name_ar, p.name_en, locale))
    .join(locale === "ar" ? "، " : ", ");

  return (
    <article
      className={`relative overflow-hidden rounded-lg border bg-white ${
        listing.is_featured ? "border-amber-400" : "border-slate-200"
      }`}
    >
      <Link href={`/listings/${listing.reference}`} className="flex flex-col">
        <div className="relative aspect-[4/3] bg-slate-100">
          {listing.cover ? (
            <Image
              src={listing.cover.card_url}
              alt={title}
              width={640}
              height={480}
              unoptimized // already resized by imgproxy
              className="size-full object-cover"
            />
          ) : null}
          {listing.is_featured && (
            <span className="absolute start-2 top-2 rounded bg-amber-500 px-2 py-0.5 text-xs font-bold text-white">
              {t("featured")}
            </span>
          )}
        </div>
        <div className="flex flex-col gap-1 p-3">
          <PriceTag
            halalas={listing.price_halalas}
            rentPeriod={listing.rent_period}
            className="text-lg font-bold text-emerald-800"
          />
          <h3 className="line-clamp-1 font-medium">{title}</h3>
          <p className="line-clamp-1 text-sm text-slate-500">{place}</p>
          <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-sm text-slate-700">
            {listing.bedrooms !== null && <li>{t("beds", { count: listing.bedrooms })}</li>}
            {listing.bathrooms !== null && <li>{t("baths", { count: listing.bathrooms })}</li>}
            <li>{t("area", { area: formatNumber(listing.area_m2, locale) })}</li>
          </ul>
        </div>
      </Link>
      <div className="absolute end-2 top-2">
        <FavouriteButton reference={listing.reference} />
      </div>
    </article>
  );
}
