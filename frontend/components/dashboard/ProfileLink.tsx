"use client";

import { type ReactNode, useEffect, useState } from "react";

import { Link } from "@/i18n/navigation";
import { api } from "@/lib/api/client";

/** The dashboard's "Profile" button: agency admins edit their agency, everyone else their broker profile. */
export default function ProfileLink({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  const [href, setHref] = useState("/account/broker-profile");

  useEffect(() => {
    api
      .me()
      .then((me) => {
        if (me.role === "agency_admin") setHref("/account/agency");
      })
      .catch(() => {
        // Not logged in: the dashboard gate already shows the next step.
      });
  }, []);

  return (
    <Link href={href} className={className}>
      {children}
    </Link>
  );
}
