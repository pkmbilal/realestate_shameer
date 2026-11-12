import type { MetadataRoute } from "next";

import { allowIndexing, siteUrl } from "@/lib/config";

// Read SEO_ALLOW_INDEXING when the request comes in, not when the image is built.
export const dynamic = "force-dynamic";

export default function robots(): MetadataRoute.Robots {
  if (!allowIndexing) {
    // Local and staging copies must never be indexed.
    return { rules: { userAgent: "*", disallow: "/" } };
  }
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/api/", "/*/dashboard", "/*/account", "/*/login"],
    },
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
