"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api/client";

const POLL_MS = 3000;

type Step =
  | { name: "loading" }
  | { name: "form" }
  | { name: "waiting"; ref: string; number: string }
  | { name: "approved" }
  | { name: "failed"; reason: "rejected" | "expired" };

const KNOWN_ERRORS = ["invalid_national_id", "already_verified", "rate_limited"] as const;
type ErrorKey = (typeof KNOWN_ERRORS)[number] | "generic";

function errorKey(error: unknown): ErrorKey {
  if (error instanceof ApiError && error.status === 429) return "rate_limited";
  const code = error instanceof ApiError ? error.code : undefined;
  return KNOWN_ERRORS.find((known) => known === code) ?? "generic";
}

/** National ID → number to tap in the Nafath app → wait for approval. */
export default function NafathVerifyForm() {
  const t = useTranslations("Verify");
  const router = useRouter();
  const [step, setStep] = useState<Step>({ name: "loading" });
  const [nationalId, setNationalId] = useState("");
  const [error, setError] = useState<ErrorKey | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .me()
      .then((me) => setStep(me.is_nafath_verified ? { name: "approved" } : { name: "form" }))
      .catch(() => router.replace("/login"));
  }, [router]);

  const waitingRef = step.name === "waiting" ? step.ref : null;
  useEffect(() => {
    if (!waitingRef) return;
    const timer = setInterval(() => {
      api.nafath
        .status(waitingRef)
        .then(({ status }) => {
          if (status === "approved") setStep({ name: "approved" });
          else if (status !== "pending") setStep({ name: "failed", reason: status });
        })
        .catch(() => undefined); // keep polling; a network blip is not a failure
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [waitingRef]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const started = await api.nafath.start(nationalId);
      // Forget the ID as soon as Nafath has it.
      setNationalId("");
      setStep({ name: "waiting", ref: started.transaction_ref, number: started.random_number });
    } catch (err) {
      const key = errorKey(err);
      if (key === "already_verified") setStep({ name: "approved" });
      else setError(key);
    } finally {
      setBusy(false);
    }
  }

  if (step.name === "loading") return <div className="h-40" aria-busy />;

  if (step.name === "approved") {
    return (
      <div className="flex flex-col gap-4">
        <p role="status" className="rounded-md bg-emerald-50 px-4 py-3 text-emerald-800">
          {t("approved")}
        </p>
        <Link
          href="/account/broker-profile"
          className="rounded-lg bg-emerald-600 px-4 py-3 text-center font-medium text-white hover:bg-emerald-700"
        >
          {t("continueToProfile")}
        </Link>
      </div>
    );
  }

  if (step.name === "waiting") {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-slate-600">{t("openApp")}</p>
        <span
          dir="ltr"
          className="flex size-24 items-center justify-center rounded-full border-4 border-emerald-600 text-4xl font-bold text-emerald-700"
        >
          {step.number}
        </span>
        <p role="status" className="text-sm text-slate-500">
          {t("waiting")}
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {step.name === "failed" && (
        <p role="alert" className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t(`failed.${step.reason}`)}
        </p>
      )}
      <label className="flex flex-col gap-2">
        <span className="font-medium">{t("nationalIdLabel")}</span>
        <input
          type="text"
          inputMode="numeric"
          autoComplete="off"
          dir="ltr"
          maxLength={10}
          required
          value={nationalId}
          onChange={(e) => setNationalId(e.target.value.replace(/\D/g, ""))}
          className="w-full rounded-lg border border-slate-300 px-4 py-3 text-start text-lg tracking-wide focus:border-emerald-600 focus:outline-none"
        />
        <span className="text-sm text-slate-500">{t("nationalIdHint")}</span>
      </label>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {t(`errors.${error}`)}
        </p>
      )}

      <button
        type="submit"
        disabled={busy || nationalId.length !== 10}
        className="rounded-lg bg-emerald-600 px-4 py-3 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
      >
        {t("submit")}
      </button>
    </form>
  );
}
