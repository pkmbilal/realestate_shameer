import { useTranslations } from "next-intl";

import CityList from "@/components/locations/CityList";
import SiteHeader from "@/components/SiteHeader";
import { Link } from "@/i18n/navigation";
import { api, type City } from "@/lib/api/client";
import { portalName } from "@/lib/config";

async function isApiHealthy() {
  try {
    return (await api.health()).status === "ok";
  } catch {
    return false;
  }
}

async function loadCities(): Promise<City[]> {
  try {
    return await api.locations.cities();
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const [healthy, cities] = await Promise.all([isApiHealthy(), loadCities()]);
  return <HomeContent healthy={healthy} cities={cities} />;
}

function HomeContent({ healthy, cities }: { healthy: boolean; cities: City[] }) {
  const t = useTranslations("Home");
  const tn = useTranslations("Nav");

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col px-4 py-6 sm:px-6">
      <SiteHeader />

      <section className="flex flex-1 flex-col justify-center gap-4 py-16">
        <span className="w-fit rounded-full bg-emerald-50 px-3 py-1 text-sm font-medium text-emerald-700">
          {t("comingSoon")}
        </span>
        <h1 className="text-3xl leading-tight font-bold sm:text-5xl">{portalName}</h1>
        <p className="text-lg text-slate-600">{t("tagline")}</p>
        <div className="flex flex-wrap gap-3 pt-2">
          <Link
            href="/search?purpose=sale"
            className="rounded-md bg-emerald-600 px-5 py-2.5 font-medium text-white hover:bg-emerald-700"
          >
            {tn("buy")}
          </Link>
          <Link
            href="/search?purpose=rent"
            className="rounded-md bg-emerald-600 px-5 py-2.5 font-medium text-white hover:bg-emerald-700"
          >
            {tn("rent")}
          </Link>
          <Link
            href="/search"
            className="rounded-md border border-slate-300 px-5 py-2.5 font-medium hover:bg-slate-50"
          >
            {t("browseAll")}
          </Link>
        </div>
      </section>

      <div className="pb-12">
        <CityList cities={cities} />
      </div>

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
