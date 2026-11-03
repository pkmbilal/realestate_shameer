"use client";

import { useTranslations } from "next-intl";
import { type FormEvent, useEffect, useState } from "react";

import { useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api/client";

const KNOWN_ERRORS = [
  "invalid_phone",
  "invalid_code",
  "too_many_attempts",
  "rate_limited",
  "account_disabled",
] as const;

type ErrorKey = (typeof KNOWN_ERRORS)[number] | "generic";

function errorKey(error: unknown): ErrorKey {
  if (error instanceof ApiError && error.status === 429) return "rate_limited";
  const code = error instanceof ApiError ? error.code : undefined;
  return KNOWN_ERRORS.find((known) => known === code) ?? "generic";
}

/** Only same-site paths like "/search?x=1" are allowed as the after-login page. */
function safeNext(next: string | undefined): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/";
}

/** Two steps: enter phone → enter the 6-digit SMS code. `next` is where to go afterwards. */
export default function OtpLoginForm({ next }: { next?: string }) {
  const t = useTranslations("Login");
  const router = useRouter();
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<ErrorKey | null>(null);
  const [busy, setBusy] = useState(false);
  const [resendIn, setResendIn] = useState(0);

  useEffect(() => {
    if (resendIn <= 0) return;
    const timer = setTimeout(() => setResendIn((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [resendIn]);

  async function sendCode() {
    setBusy(true);
    setError(null);
    try {
      const { resend_after } = await api.auth.requestOtp(phone);
      setStep("code");
      setCode("");
      setResendIn(resend_after);
    } catch (err) {
      setError(errorKey(err));
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setBusy(true);
    setError(null);
    try {
      await api.auth.verifyOtp(phone, code);
      router.replace(safeNext(next));
      router.refresh();
    } catch (err) {
      setError(errorKey(err));
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (step === "phone") void sendCode();
    else void verify();
  }

  const inputClass =
    "w-full rounded-lg border border-slate-300 px-4 py-3 text-lg tracking-wide focus:border-emerald-600 focus:outline-none";

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      {step === "phone" ? (
        <label className="flex flex-col gap-2">
          <span className="font-medium">{t("phoneLabel")}</span>
          <input
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            dir="ltr"
            required
            placeholder={t("phonePlaceholder")}
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className={`${inputClass} text-start`}
          />
          <span className="text-sm text-slate-500">{t("phoneHint")}</span>
        </label>
      ) : (
        <label className="flex flex-col gap-2">
          <span className="font-medium">{t("codeLabel")}</span>
          <span className="text-sm text-slate-500">
            {t("codeSentTo")}{" "}
            <span dir="ltr" className="font-medium text-slate-700">
              {phone}
            </span>
          </span>
          <input
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            dir="ltr"
            maxLength={6}
            required
            autoFocus
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className={`${inputClass} text-center tracking-[0.5em]`}
          />
        </label>
      )}

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {t(`errors.${error}`)}
        </p>
      )}

      <button
        type="submit"
        disabled={busy || (step === "phone" ? phone.trim() === "" : code.length !== 6)}
        className="rounded-lg bg-emerald-600 px-4 py-3 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
      >
        {step === "phone" ? t("sendCode") : t("verify")}
      </button>

      {step === "code" && (
        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={() => {
              setStep("phone");
              setError(null);
            }}
            className="text-slate-600 underline"
          >
            {t("changePhone")}
          </button>
          <button
            type="button"
            onClick={() => void sendCode()}
            disabled={busy || resendIn > 0}
            className="text-emerald-700 underline disabled:text-slate-400 disabled:no-underline"
          >
            {resendIn > 0 ? t("resendIn", { seconds: resendIn }) : t("resend")}
          </button>
        </div>
      )}
    </form>
  );
}
