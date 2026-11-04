"use client";

import { useTranslations } from "next-intl";
import { type ReactNode, useEffect, useState } from "react";

import { Link } from "@/i18n/navigation";
import { api, ApiError, type Me } from "@/lib/api/client";

type Gate =
  | { state: "loading" }
  | { state: "error" }
  | { state: "login" }
  | { state: "verify" }
  | { state: "profile" }
  | { state: "ready" };

/**
 * Shows the dashboard only to people who may post listings: logged in, verified through
 * Nafath, and an owner, broker (with a profile) or agency admin. Everyone else gets a
 * short explanation and a link to the next step. Runs in the browser because the login
 * cookie belongs to the API.
 */
export default function AdvertiserGate({
  next,
  children,
}: {
  /** Where to come back to after logging in, e.g. "/dashboard". */
  next: string;
  /** Rendered (and so allowed to load its data) only once the checks pass. */
  children: ReactNode;
}) {
  const t = useTranslations("Dashboard.gate");
  const [gate, setGate] = useState<Gate>({ state: "loading" });

  useEffect(() => {
    async function check(): Promise<Gate> {
      let me: Me;
      try {
        me = await api.me();
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return { state: "login" };
        return { state: "error" };
      }
      if (!me.is_nafath_verified) return { state: "verify" };
      if (me.role === "buyer") return { state: "profile" };
      if (me.role === "broker") {
        try {
          await api.brokers.me();
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) return { state: "profile" };
          return { state: "error" };
        }
      }
      return { state: "ready" };
    }
    void check().then(setGate);
  }, []);

  if (gate.state === "loading") return <div className="h-40" aria-busy />;
  if (gate.state === "ready") return <>{children}</>;
  if (gate.state === "error") {
    return <p className="rounded-lg bg-red-50 p-4 text-red-700">{t("error")}</p>;
  }

  const step = {
    login: { text: t("loginNeeded"), cta: t("login"), href: `/login?next=${encodeURIComponent(next)}` },
    verify: { text: t("verifyNeeded"), cta: t("verify"), href: "/account/verify" },
    profile: { text: t("profileNeeded"), cta: t("profile"), href: "/account/broker-profile" },
  }[gate.state];

  return (
    <div className="flex flex-col items-start gap-4">
      <p className="rounded-md bg-amber-50 px-4 py-3 text-amber-800">{step.text}</p>
      <Link
        href={step.href}
        className="rounded-lg bg-emerald-600 px-4 py-3 font-medium text-white hover:bg-emerald-700"
      >
        {step.cta}
      </Link>
    </div>
  );
}
