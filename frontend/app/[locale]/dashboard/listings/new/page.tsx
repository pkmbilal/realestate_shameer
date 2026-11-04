import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import AdvertiserGate from "@/components/dashboard/AdvertiserGate";
import DashboardShell from "@/components/dashboard/DashboardShell";
import StartListingForm from "@/components/dashboard/StartListingForm";
import { routing } from "@/i18n/routing";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "Dashboard.start" });
  return { title: t("title"), robots: { index: false } };
}

export default async function NewListingPage({ params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const t = await getTranslations("Dashboard.start");

  return (
    <DashboardShell title={t("title")} intro={t("intro")}>
      <div className="w-full max-w-md">
        <AdvertiserGate next="/dashboard/listings/new">
          <StartListingForm />
        </AdvertiserGate>
      </div>
    </DashboardShell>
  );
}
