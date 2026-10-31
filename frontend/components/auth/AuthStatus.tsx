"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { api, type Me } from "@/lib/api/client";

/** Header item: "Log in" for visitors, or the masked phone and "Log out" for logged-in users. */
export default function AuthStatus() {
  const t = useTranslations("Auth");
  const router = useRouter();
  // undefined = still checking, null = logged out.
  const [me, setMe] = useState<Me | null | undefined>(undefined);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch(() => setMe(null));
  }, []);

  async function logout() {
    await api.auth.logout().catch(() => undefined);
    setMe(null);
    router.refresh();
  }

  if (me === undefined) return <span className="h-8 w-16" aria-hidden />;

  if (me === null) {
    return (
      <Link
        href="/login"
        className="rounded-md bg-emerald-600 px-3 py-1.5 whitespace-nowrap text-sm font-medium text-white hover:bg-emerald-700"
      >
        {t("login")}
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <span dir="ltr" className="hidden text-slate-600 sm:inline">
        {me.masked_phone}
      </span>
      <button
        type="button"
        onClick={logout}
        className="rounded-md border border-slate-300 px-3 py-1.5 font-medium whitespace-nowrap hover:bg-slate-50"
      >
        {t("logout")}
      </button>
    </div>
  );
}
