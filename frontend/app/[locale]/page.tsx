import { useTranslations } from "next-intl";

import LocaleSwitcher from "@/components/LocaleSwitcher";
import { api } from "@/lib/api/client";
import { portalName } from "@/lib/config";

async function isApiHealthy() {
  try {
    return (await api.health()).status === "ok";
  } catch {
    return false;
  }
}

export default async function HomePage() {
  const healthy = await isApiHealthy();
  return <HomeContent healthy={healthy} />;
}

function HomeContent({ healthy }: { healthy: boolean }) {
  const t = useTranslations("Home");

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col px-4 py-6 sm:px-6">
      <header className="flex items-center justify-between">
        <span className="text-lg font-bold">{portalName}</span>
        <LocaleSwitcher />
      </header>

      <section className="flex flex-1 flex-col justify-center gap-4 py-16">
        <span className="w-fit rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
          {t("comingSoon")}
        </span>
        <h1 className="text-3xl leading-tight font-bold sm:text-5xl">{portalName}</h1>
        <p className="text-lg text-slate-600">{t("tagline")}</p>
      </section>

      <footer className="flex items-center gap-2 text-sm text-slate-500">
        <span
          aria-hidden
          className={`inline-block size-2 rounded-full ${healthy ? "bg-emerald-500" : "bg-red-500"}`}
        />
        <span>
          {t("apiStatus")}: {healthy ? t("statusOk") : t("statusDown")}
        </span>
      </footer>
    </main>
  );
}
