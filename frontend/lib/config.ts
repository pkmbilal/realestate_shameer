// Brand name placeholder until it is decided. Read on the server from the PORTAL_NAME env var.
export const portalName = process.env.PORTAL_NAME ?? "PORTAL_NAME";

// Public site address for canonical URLs, hreflang and JSON-LD (server only).
export const siteUrl = (process.env.SITE_URL ?? "http://localhost:3000").replace(/\/$/, "");

// Map style for MapLibre. OpenFreeMap needs no API key.
export const mapStyleUrl =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/liberty";
