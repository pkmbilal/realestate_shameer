/**
 * Default Open Graph image (1200×630), used when a page has no photo of its own.
 * Latin text only: the image renderer cannot join Arabic letters correctly.
 */
import { ImageResponse } from "next/og";

import { portalName } from "@/lib/config";

export const dynamic = "force-dynamic"; // PORTAL_NAME is read at runtime, not build time

export function GET() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "linear-gradient(135deg, #064e3b 0%, #059669 100%)",
          color: "white",
        }}
      >
        <div style={{ fontSize: 88, fontWeight: 700 }}>{portalName}</div>
        <div style={{ fontSize: 40, marginTop: 24, opacity: 0.9 }}>
          Licensed property listings in Saudi Arabia
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      headers: { "Cache-Control": "public, max-age=86400" },
    },
  );
}
