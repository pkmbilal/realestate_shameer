"use client";

import Image from "next/image";
import { useTranslations } from "next-intl";
import { type ChangeEvent, useRef, useState } from "react";

import { api, type MyListing, uploadToStorage } from "@/lib/api/client";

import { type DashboardErrorKey, dashboardErrorKey } from "./errors";

const ACCEPT = "image/jpeg,image/png,image/webp";

type Props = {
  listing: MyListing;
  editable: boolean;
  /** Called with the fresh listing after photos change (status and missing fields may change too). */
  onListing: (listing: MyListing) => void;
};

/**
 * Upload, reorder and delete listing photos. Files go straight from the browser to file
 * storage through a short-lived presigned URL, then the API records them. The first photo
 * is the cover.
 */
export default function PhotoManager({ listing, editable, onListing }: Props) {
  const t = useTranslations("Dashboard.photos");
  const te = useTranslations("Dashboard.errors");
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<DashboardErrorKey | null>(null);
  const photos = listing.photos;
  const ref = listing.reference;

  async function onFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = ""; // allow picking the same file again
    if (files.length === 0) return;
    setBusy(true);
    setError(null);
    setProgress({ done: 0, total: files.length });
    for (const [index, file] of files.entries()) {
      try {
        const upload = await api.myListings.presignPhoto(ref, file);
        await uploadToStorage(upload, file);
        await api.myListings.confirmPhoto(ref, upload.key);
      } catch (err) {
        const key = dashboardErrorKey(err);
        setError(key);
        if (key === "too_many_photos") break;
      }
      setProgress({ done: index + 1, total: files.length });
    }
    await reload();
    setProgress(null);
    setBusy(false);
  }

  async function reload() {
    try {
      onListing(await api.myListings.get(ref));
    } catch {
      setError("generic");
    }
  }

  async function move(index: number, delta: -1 | 1) {
    const ids = photos.map((p) => p.id);
    const moved = ids.splice(index, 1);
    ids.splice(index + delta, 0, ...moved);
    setBusy(true);
    setError(null);
    try {
      onListing(await api.myListings.reorderPhotos(ref, ids));
    } catch (err) {
      setError(dashboardErrorKey(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(photoId: number) {
    setBusy(true);
    setError(null);
    try {
      await api.myListings.deletePhoto(ref, photoId);
    } catch (err) {
      setError(dashboardErrorKey(err));
    }
    await reload();
    setBusy(false);
  }

  const iconButton =
    "flex size-8 items-center justify-center rounded-md bg-white/90 text-slate-800 shadow hover:bg-white disabled:opacity-40";

  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{t("title")}</h2>
          <p className="text-sm text-slate-500">{t("hint")}</p>
        </div>
        {editable && (
          <>
            <input
              ref={input}
              type="file"
              accept={ACCEPT}
              multiple
              className="hidden"
              onChange={onFiles}
            />
            <button
              type="button"
              disabled={busy}
              onClick={() => input.current?.click()}
              className="rounded-lg border border-emerald-600 px-4 py-2 font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
            >
              {t("add")}
            </button>
          </>
        )}
      </div>

      {progress && (
        <p role="status" className="text-sm text-slate-600">
          {t("uploading", progress)}
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {te(error)}
        </p>
      )}

      {photos.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-slate-500">
          {t("none")}
        </p>
      ) : (
        <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {photos.map((photo, index) => (
            <li key={photo.id} className="relative overflow-hidden rounded-lg bg-slate-100">
              <Image
                src={photo.card_url}
                alt={t("alt", { n: index + 1 })}
                width={640}
                height={480}
                unoptimized // already resized by imgproxy
                className="aspect-[4/3] w-full object-cover"
              />
              {index === 0 && (
                <span className="absolute start-2 top-2 rounded bg-emerald-600 px-2 py-0.5 text-xs font-bold text-white">
                  {t("cover")}
                </span>
              )}
              {editable && (
                <div className="absolute inset-x-2 bottom-2 flex justify-between gap-1">
                  <div className="flex gap-1">
                    <button
                      type="button"
                      className={iconButton}
                      disabled={busy || index === 0}
                      onClick={() => move(index, -1)}
                      aria-label={t("moveEarlier")}
                      title={t("moveEarlier")}
                    >
                      <Chevron className="rtl:-scale-x-100" />
                    </button>
                    <button
                      type="button"
                      className={iconButton}
                      disabled={busy || index === photos.length - 1}
                      onClick={() => move(index, 1)}
                      aria-label={t("moveLater")}
                      title={t("moveLater")}
                    >
                      <Chevron className="ltr:-scale-x-100" />
                    </button>
                  </div>
                  <button
                    type="button"
                    className={`${iconButton} text-red-700`}
                    disabled={busy}
                    onClick={() => remove(photo.id)}
                    aria-label={t("delete")}
                    title={t("delete")}
                  >
                    <svg viewBox="0 0 24 24" aria-hidden className="size-4 fill-current">
                      <path d="M9 3h6l1 2h4v2H4V5h4l1-2zm-3 6h12l-1 12H7L6 9z" />
                    </svg>
                  </button>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

/** A left-pointing chevron; flip it with a class for the other direction. */
function Chevron({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={`size-4 fill-current ${className}`}>
      <path d="m15.4 7.4-1.4-1.4-6 6 6 6 1.4-1.4-4.6-4.6z" />
    </svg>
  );
}
