/**
 * Shared layout for the Terms, Privacy and REGA licence pages.
 * The text lives in messages/{ar,en}.json under "Legal.<page>" so the owner can replace the
 * placeholder wording without touching code.
 */
import type { Metadata } from "next";
import { useLocale, useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";

import SiteHeader from "@/components/SiteHeader";
import type { Locale } from "@/i18n/routing";
import { formatDate } from "@/lib/format";
import { LEGAL_SLUGS, type LegalPageKey } from "@/lib/legal";
import { languageAlternates, openGraph, robotsFor } from "@/lib/seo/meta";

type Section = { heading: string; paragraphs: string[] };

export async function legalMetadata(locale: Locale, page: LegalPageKey): Promise<Metadata> {
  const t = await getTranslations({ locale, namespace: "Legal" });
  const slug = LEGAL_SLUGS[page];
  const title = t(`${page}.title`);
  const description = t(`${page}.description`);
  return {
    title,
    description,
    alternates: {
      canonical: `/${locale}/${slug}`,
      languages: languageAlternates((l) => `/${l}/${slug}`),
    },
    robots: robotsFor(true),
    openGraph: openGraph(locale, { title, description, url: `/${locale}/${slug}` }),
  };
}

type Props = { page: LegalPageKey; children?: React.ReactNode };

export default function LegalPage({ page, children }: Props) {
  const t = useTranslations("Legal");
  const locale = useLocale();
  const sections = t.raw(`${page}.sections`) as Section[];
  const isDraft = t.raw(`${page}.draft`) === true;

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col px-4 py-6 sm:px-6">
      <SiteHeader />
      <article className="flex flex-col gap-6 py-8">
        <header className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold">{t(`${page}.title`)}</h1>
          <p className="text-sm text-slate-500">
            {t("lastUpdated", { date: formatDate(t(`${page}.updated`), locale) })}
          </p>
        </header>

        {isDraft && (
          <p
            role="note"
            className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
          >
            {t("draftNotice")}
          </p>
        )}

        {children}

        {sections.map((section) => (
          <section key={section.heading} className="flex flex-col gap-2">
            <h2 className="text-lg font-bold">{section.heading}</h2>
            {section.paragraphs.map((paragraph, i) => (
              <p key={i} className="leading-relaxed text-slate-700">
                {paragraph}
              </p>
            ))}
          </section>
        ))}
      </article>
    </main>
  );
}
