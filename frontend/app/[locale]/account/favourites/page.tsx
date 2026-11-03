import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale, useTranslations } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import FavouritesList from "@/components/favourites/FavouritesList";
import FavouritesProvider from "@/components/favourites/FavouritesProvider";
import SiteHeader from "@/components/SiteHeader";
import { routing } from "@/i18n/routing";

type Props = { params: Promise<{ locale: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "Favourites" });
  return { title: t("title"), robots: { index: false } };
}

export default async function FavouritesPage({ params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  return <FavouritesContent />;
}

function FavouritesContent() {
  const t = useTranslations("Favourites");
  return (
    <FavouritesProvider>
      <main className="mx-auto flex min-h-dvh max-w-5xl flex-col gap-6 px-4 py-6 sm:px-6">
        <SiteHeader />
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <FavouritesList />
      </main>
    </FavouritesProvider>
  );
}
