import { defineRouting } from "next-intl/routing";

// Arabic is the default locale; every URL starts with /ar or /en.
// localeDetection is off so "/" always opens Arabic, whatever the browser language is.
export const routing = defineRouting({
  locales: ["ar", "en"],
  defaultLocale: "ar",
  localeDetection: false,
});

export type Locale = (typeof routing.locales)[number];

export const rtlLocales: readonly Locale[] = ["ar"];
