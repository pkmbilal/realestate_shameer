import AuthStatus from "@/components/auth/AuthStatus";
import LocaleSwitcher from "@/components/LocaleSwitcher";
import { Link } from "@/i18n/navigation";
import { portalName } from "@/lib/config";

export default function SiteHeader() {
  return (
    <header className="flex items-center justify-between gap-3">
      <Link href="/" className="min-w-0 truncate text-lg font-bold">
        {portalName}
      </Link>
      <div className="flex shrink-0 items-center gap-2">
        <AuthStatus />
        <LocaleSwitcher />
      </div>
    </header>
  );
}
