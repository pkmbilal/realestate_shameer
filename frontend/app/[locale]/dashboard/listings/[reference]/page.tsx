import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import AdvertiserGate from "@/components/dashboard/AdvertiserGate";
import DashboardShell from "@/components/dashboard/DashboardShell";
import ListingEditor from "@/components/dashboard/ListingEditor";
import { routing } from "@/i18n/routing";

type Props = { params: Promise<{ locale: string; reference: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "Dashboard.editor" });
  return { title: t("title"), robots: { index: false } };
}

export default async function EditListingPage({ params }: Props) {
  const { locale, reference } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  // Listing references are 8 upper-case letters/digits (see backend listings/urls.py).
  if (!/^[2-9A-HJ-NP-Z]{8}$/.test(reference)) notFound();
  setRequestLocale(locale);
  const t = await getTranslations("Dashboard.editor");

  return (
    <DashboardShell title={t("title")}>
      <AdvertiserGate next={`/dashboard/listings/${reference}`}>
        <ListingEditor reference={reference} />
      </AdvertiserGate>
    </DashboardShell>
  );
}
