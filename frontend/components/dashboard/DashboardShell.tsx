import type { ReactNode } from "react";

import SiteHeader from "@/components/SiteHeader";

/** Page frame shared by the dashboard pages: header, title, optional intro and actions. */
export default function DashboardShell({
  title,
  intro,
  actions,
  children,
}: {
  title: string;
  intro?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-4xl flex-col gap-6 px-4 py-6 sm:px-6">
      <SiteHeader />
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-bold">{title}</h1>
          {intro && <p className="text-slate-600">{intro}</p>}
        </div>
        {actions}
      </div>
      {children}
    </main>
  );
}
