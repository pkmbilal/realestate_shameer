import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { hasLocale, useTranslations } from "next-intl";
import { getTranslations, setRequestLocale } from "next-intl/server";

import OtpLoginForm from "@/components/auth/OtpLoginForm";
import SiteHeader from "@/components/SiteHeader";
import { routing } from "@/i18n/routing";

type Props = {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ next?: string | string[] }>;
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) return {};
  const t = await getTranslations({ locale, namespace: "Login" });
  // Login pages should not appear in search results.
  return { title: t("title"), robots: { index: false } };
}

export default async function LoginPage({ params, searchParams }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const { next } = await searchParams;
  return <LoginContent next={typeof next === "string" ? next : undefined} />;
}

function LoginContent({ next }: { next?: string }) {
  const t = useTranslations("Login");

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col px-4 py-6 sm:px-6">
      <SiteHeader />
      <section className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-6 py-12">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-slate-600">{t("intro")}</p>
        </div>
        <OtpLoginForm next={next} />
      </section>
    </main>
  );
}
