import { useTranslations } from "next-intl";

import { LEGAL_SLUGS } from "@/lib/legal";
import { Link } from "@/i18n/navigation";
import { portalName, regaPlatformLicence } from "@/lib/config";

/** Site-wide footer: legal links and the platform's REGA licence number. */
export default function SiteFooter() {
  const t = useTranslations("Footer");
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-slate-200 bg-slate-50">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-6 text-sm text-slate-600 sm:px-6">
        <nav aria-label={t("legalNav")} className="flex flex-wrap gap-x-4 gap-y-2">
          <Link href={`/${LEGAL_SLUGS.terms}`} className="hover:underline">
            {t("terms")}
          </Link>
          <Link href={`/${LEGAL_SLUGS.privacy}`} className="hover:underline">
            {t("privacy")}
          </Link>
          <Link href={`/${LEGAL_SLUGS.rega}`} className="hover:underline">
            {t("rega")}
          </Link>
        </nav>
        <p>
          {regaPlatformLicence ? (
            <>
              {t("regaLicence")}{" "}
              <bdi dir="ltr" className="font-mono font-bold">
                {regaPlatformLicence}
              </bdi>
            </>
          ) : (
            t("regaLicencePending")
          )}
        </p>
        <p>{t("copyright", { year, name: portalName })}</p>
      </div>
    </footer>
  );
}
