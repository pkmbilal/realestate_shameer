import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // Run on every page except Next.js internals and files with an extension (images, etc.).
  matcher: "/((?!api|_next|_vercel|.*\\..*).*)",
};
