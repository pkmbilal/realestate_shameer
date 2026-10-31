import type { Locale } from "@/i18n/routing";
import type messages from "@/messages/en.json";

// Makes translation keys type-checked: a typo in t("...") fails `npm run typecheck`.
declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: typeof messages;
  }
}
