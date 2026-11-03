import Image from "next/image";
import { useTranslations } from "next-intl";

import type { Photo } from "@/lib/api/client";

/** Swipeable photo strip (CSS scroll-snap, no JavaScript). The cover photo comes first. */
export default function Gallery({ photos, title }: { photos: Photo[]; title: string }) {
  const t = useTranslations("Listing");

  if (photos.length === 0) {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-lg bg-slate-100 text-slate-500 sm:aspect-[16/9]">
        {t("noPhotos")}
      </div>
    );
  }

  return (
    <ul className="flex snap-x snap-mandatory gap-2 overflow-x-auto rounded-lg">
      {photos.map((photo, index) => (
        <li
          key={photo.id}
          className="relative aspect-[4/3] w-full shrink-0 snap-center overflow-hidden rounded-lg bg-slate-100 sm:aspect-[16/9]"
        >
          <Image
            src={photo.large_url}
            alt={`${title} — ${t("photoAlt", { n: index + 1, total: photos.length })}`}
            width={1600}
            height={1200}
            unoptimized // already resized by imgproxy
            priority={index === 0}
            className="size-full object-cover"
          />
          <span
            dir="ltr"
            className="absolute end-2 bottom-2 rounded bg-black/60 px-2 py-0.5 text-xs text-white"
          >
            {index + 1} / {photos.length}
          </span>
        </li>
      ))}
    </ul>
  );
}
