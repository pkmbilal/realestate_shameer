import AuthStatus from "@/components/auth/AuthStatus";
import LocaleSwitcher from "@/components/LocaleSwitcher";
import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { portalName } from "@/lib/config";

export default function SiteHeader() {
  const t = useTranslations("Nav");
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
      <Link href="/" className="max-w-full truncate text-lg font-bold">
        {portalName}
      </Link>
      <div className="flex shrink-0 items-center gap-2">
        <Link
          href="/search"
          className="hidden px-2 py-1.5 text-sm font-medium whitespace-nowrap hover:underline sm:inline"
        >
          {t("search")}
        </Link>
        <AuthStatus />
        <LocaleSwitcher />
      </div>
    </header>
  );
}
