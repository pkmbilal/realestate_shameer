"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import MapView, { type Bounds, type MapMarker } from "@/components/map/Map";
import { useRouter } from "@/i18n/navigation";
import { api, type MapPin, type SearchParams } from "@/lib/api/client";
import { formatSarShort } from "@/lib/format";

// Dammam / Khobar, the centre of the launch market.
const DEFAULT_CENTER = { lng: 50.1, lat: 26.35 };
const MAX_PINS = 500;

type Props = {
  /** Current filters (without bbox/page); pins follow them. */
  params: SearchParams;
  center?: { lng: number; lat: number } | null;
  className?: string;
};

const DESKTOP = "(min-width: 1024px)";

function useIsDesktop(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const query = window.matchMedia(DESKTOP);
      query.addEventListener("change", onChange);
      return () => query.removeEventListener("change", onChange);
    },
    () => window.matchMedia(DESKTOP).matches,
    () => false,
  );
}

/**
 * Desktop always shows the map beside the list. On phones it is only created when the
 * visitor picks the Map view, so list browsing doesn't download map tiles.
 */
export default function SearchMapPanel({ mobileVisible, ...props }: Props & { mobileVisible: boolean }) {
  const isDesktop = useIsDesktop();
  if (!isDesktop && !mobileVisible) return null;
  return <SearchMap {...props} />;
}

/** Map of the search results. Loads light pins for the visible area after each pan/zoom. */
function SearchMap({ params, center, className }: Props) {
  const t = useTranslations("Search");
  const locale = useLocale();
  const router = useRouter();
  const [pins, setPins] = useState<MapPin[]>([]);
  const [truncated, setTruncated] = useState(false);
  const lastBounds = useRef<Bounds | null>(null);
  const requestId = useRef(0);

  const paramsKey = JSON.stringify(params);

  const load = useCallback(
    (bounds: Bounds) => {
      lastBounds.current = bounds;
      const id = ++requestId.current;
      const bbox = bounds.map((n) => n.toFixed(5)).join(",");
      api.listings
        .map({ ...(JSON.parse(paramsKey) as SearchParams), bbox })
        .then((data) => {
          if (id !== requestId.current) return; // a newer request already answered
          setPins(data.results);
          setTruncated(data.truncated);
        })
        .catch(() => undefined);
    },
    [paramsKey],
  );

  // Filters changed: reload pins for the area already on screen.
  useEffect(() => {
    if (lastBounds.current) load(lastBounds.current);
  }, [load]);

  const markers = useMemo<MapMarker[]>(
    () =>
      pins.map((pin) => ({
        id: pin.reference,
        lng: pin.longitude,
        lat: pin.latitude,
        label: pin.price_halalas === null ? "" : formatSarShort(pin.price_halalas, locale),
        highlighted: pin.is_featured,
      })),
    [pins, locale],
  );

  return (
    <div className={`relative ${className ?? ""}`}>
      <MapView
        className="size-full"
        center={center ?? DEFAULT_CENTER}
        zoom={center ? 12 : 10}
        markers={markers}
        onBoundsChange={load}
        onMarkerClick={(reference) => router.push(`/listings/${reference}`)}
        loadingText={t("mapLoading")}
        errorText={t("mapError")}
      />
      {truncated && (
        <p className="absolute inset-x-3 top-3 rounded-md bg-white/95 px-3 py-2 text-center text-xs text-slate-700 shadow">
          {t("mapTruncated", { count: MAX_PINS })}
        </p>
      )}
    </div>
  );
}
