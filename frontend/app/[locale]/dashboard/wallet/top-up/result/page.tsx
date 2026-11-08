import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import AdvertiserGate from "@/components/dashboard/AdvertiserGate";
import DashboardShell from "@/components/dashboard/DashboardShell";
import TopUpResult from "@/components/dashboard/TopUpResult";
import { routing } from "@/i18n/routing";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ payment?: string }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "Dashboard.TopUp.Result" });
  return { title: t("title"), robots: { index: false } };
}

/** The payment gateway sends the browser back here with ?payment=<id>. */
export default async function TopUpResultPage({ params, searchParams }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const paymentId = Number((await searchParams).payment);
  if (!Number.isInteger(paymentId) || paymentId <= 0) notFound();
  const t = await getTranslations("Dashboard.TopUp.Result");

  return (
    <DashboardShell title={t("title")}>
      <AdvertiserGate next={`/dashboard/wallet/top-up/result?payment=${paymentId}`}>
        <TopUpResult paymentId={paymentId} />
      </AdvertiserGate>
    </DashboardShell>
  );
}
