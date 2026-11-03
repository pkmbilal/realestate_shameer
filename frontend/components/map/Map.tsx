"use client";

/**
 * The only component that talks to the map library (MapLibre GL). Everything else uses
 * this wrapper, so switching to Mapbox or Google later means changing this file only.
 *
 * The library is loaded in the browser on demand, so it never slows down server rendering.
 */

import "maplibre-gl/dist/maplibre-gl.css";

import type { Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";

import { mapStyleUrl } from "@/lib/config";

// Shapes Arabic place names correctly on the map tiles (loaded once, only when needed).
const RTL_TEXT_PLUGIN_URL =
  "https://unpkg.com/@mapbox/mapbox-gl-rtl-text@0.2.3/mapbox-gl-rtl-text.min.js";

export type MapMarker = {
  id: string;
  lng: number;
  lat: number;
  /** Short text shown inside the pin (e.g. a price). Empty shows a dot. */
  label?: string;
  highlighted?: boolean;
};

/** [minLng, minLat, maxLng, maxLat] */
export type Bounds = [number, number, number, number];

type Props = {
  center: { lng: number; lat: number };
  zoom: number;
  markers: MapMarker[];
  className?: string;
  /** Called after the user pans or zooms (and once when the map first loads). */
  onBoundsChange?: (bounds: Bounds) => void;
  onMarkerClick?: (id: string) => void;
  /** Read-only maps (e.g. on the listing page) can't be dragged on mobile by mistake. */
  interactive?: boolean;
  loadingText: string;
  errorText: string;
};

function markerElement(marker: MapMarker, onClick?: (id: string) => void): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  el.dataset.id = marker.id;
  const base =
    "rounded-full border-2 border-white font-bold shadow-md transition-transform hover:scale-110";
  if (marker.label) {
    el.textContent = marker.label;
    el.className = `${base} px-2 py-0.5 text-xs ${
      marker.highlighted ? "bg-amber-500 text-white" : "bg-emerald-700 text-white"
    }`;
  } else {
    el.className = `${base} size-4 bg-emerald-700`;
  }
  el.dir = "auto"; // "1.7 مليون" reads right-to-left, "1.7M" left-to-right
  if (onClick) el.addEventListener("click", () => onClick(marker.id));
  else el.tabIndex = -1;
  return el;
}

export default function MapView({
  center,
  zoom,
  markers,
  className,
  onBoundsChange,
  onMarkerClick,
  interactive = true,
  loadingText,
  errorText,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef<MapLibreMarker[]>([]);
  const libRef = useRef<typeof import("maplibre-gl") | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  // Keep the latest callbacks without re-creating the map.
  const onBoundsRef = useRef(onBoundsChange);
  const onClickRef = useRef(onMarkerClick);
  useEffect(() => {
    onBoundsRef.current = onBoundsChange;
    onClickRef.current = onMarkerClick;
  });

  // Create the map once.
  useEffect(() => {
    let cancelled = false;

    import("maplibre-gl")
      .then((lib) => {
        if (cancelled || !containerRef.current) return;
        libRef.current = lib;
        if (lib.getRTLTextPluginStatus() === "unavailable") {
          lib.setRTLTextPlugin(RTL_TEXT_PLUGIN_URL, true).catch(() => undefined);
        }
        const map = new lib.Map({
          container: containerRef.current,
          style: mapStyleUrl,
          center: [center.lng, center.lat],
          zoom,
          interactive,
          attributionControl: { compact: true },
        });
        if (interactive) map.addControl(new lib.NavigationControl({ showCompass: false }));
        const report = () => {
          const b = map.getBounds();
          onBoundsRef.current?.([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]);
        };
        map.on("load", () => {
          setState("ready");
          report();
        });
        map.on("moveend", report);
        map.on("error", (event: { error?: Error }) => {
          // Tile hiccups are normal; only a style that never loads is fatal.
          if (!map.isStyleLoaded() && !map.loaded()) console.warn("map error", event.error);
        });
        mapRef.current = map;
      })
      .catch(() => setState("error"));

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
    };
    // The map is created once; later center/zoom changes don't move it (the user may have).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync markers whenever the list changes.
  useEffect(() => {
    const map = mapRef.current;
    const lib = libRef.current;
    if (!map || !lib) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = markers.map((marker) =>
      new lib.Marker({
        element: markerElement(marker, onClickRef.current && ((id) => onClickRef.current?.(id))),
      })
        .setLngLat([marker.lng, marker.lat])
        .addTo(map),
    );
  }, [markers, state]);

  return (
    <div className={`relative overflow-hidden rounded-lg bg-slate-100 ${className ?? ""}`}>
      {/* Full size via height, not "absolute": MapLibre CSS forces position: relative. */}
      <div ref={containerRef} className="size-full" />
      {state !== "ready" && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-500">
          {state === "error" ? errorText : loadingText}
        </div>
      )}
    </div>
  );
}
