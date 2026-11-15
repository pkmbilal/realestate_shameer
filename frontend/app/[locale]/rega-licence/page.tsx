import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale, useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";

import LegalPage, { legalMetadata } from "@/components/legal/LegalPage";
import { routing } from "@/i18n/routing";
import { regaPlatformLicence } from "@/lib/config";

type Props = { params: Promise<{ locale: string }> };

const REGA_URL = "https://rega.gov.sa";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  return legalMetadata(locale, "rega");
}

export default async function RegaLicencePage({ params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  return (
    <LegalPage page="rega">
      <PlatformLicence />
    </LegalPage>
  );
}

/** The platform's own REGA licence (from env), plus a link to REGA to check it. */
function PlatformLicence() {
  const t = useTranslations("Legal.rega");

  return (
    <div className="flex flex-col gap-1 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
      <span className="font-bold">{t("platformLicence")}</span>
      {regaPlatformLicence ? (
        <bdi dir="ltr" className="font-mono text-lg font-bold">
          {regaPlatformLicence}
        </bdi>
      ) : (
        <span>{t("platformLicencePending")}</span>
      )}
      <a
        href={REGA_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1 font-medium underline"
      >
        {t("regaLink")}
      </a>
    </div>
  );
}
