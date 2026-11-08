import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import AdvertiserGate from "@/components/dashboard/AdvertiserGate";
import DashboardShell from "@/components/dashboard/DashboardShell";
import TopUpPackages from "@/components/dashboard/TopUpPackages";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "Dashboard.TopUp" });
  return { title: t("title"), robots: { index: false } };
}

export default async function TopUpPage({ params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const t = await getTranslations("Dashboard.TopUp");

  return (
    <DashboardShell
      title={t("title")}
      intro={t("intro")}
      actions={
        <Link
          href="/dashboard/wallet"
          className="rounded-lg border border-slate-300 px-4 py-2 font-medium hover:bg-slate-50"
        >
          {t("backToWallet")}
        </Link>
      }
    >
      <AdvertiserGate next="/dashboard/wallet/top-up">
        <TopUpPackages />
      </AdvertiserGate>
    </DashboardShell>
  );
}
