"use client";

import { useTranslations } from "next-intl";

import MapView from "@/components/map/Map";

/** Small map with one pin on the listing page. */
export default function ListingLocationMap({ lat, lng }: { lat: number; lng: number }) {
  const t = useTranslations("Search");
  return (
    <MapView
      className="h-64"
      center={{ lat, lng }}
      zoom={14}
      markers={[{ id: "listing", lat, lng }]}
      loadingText={t("mapLoading")}
      errorText={t("mapError")}
    />
  );
}
