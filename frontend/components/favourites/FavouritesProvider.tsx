"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { usePathname, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api/client";

type FavouritesContext = {
  /** undefined while loading; null when the visitor is not logged in. */
  saved: Set<string> | null | undefined;
  toggle: (reference: string) => Promise<void>;
};

const Context = createContext<FavouritesContext | null>(null);

/**
 * Loads the visitor's saved listing references once, so every heart button on the page
 * knows whether it is filled. Wrap any page that shows FavouriteButtons in this.
 */
export default function FavouritesProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [saved, setSaved] = useState<Set<string> | null | undefined>(undefined);

  useEffect(() => {
    api.favourites
      .references()
      .then(({ references }) => setSaved(new Set(references)))
      .catch(() => setSaved(null));
  }, []);

  const toggle = useCallback(
    async (reference: string) => {
      if (saved === null) {
        const next = `${pathname}${window.location.search}`;
        router.push(`/login?next=${encodeURIComponent(next)}`);
        return;
      }
      if (saved === undefined) return;
      const wasSaved = saved.has(reference);
      const update = (add: boolean) =>
        setSaved((current) => {
          const copy = new Set(current ?? []);
          if (add) copy.add(reference);
          else copy.delete(reference);
          return copy;
        });
      update(!wasSaved); // optimistic
      try {
        if (wasSaved) await api.favourites.remove(reference);
        else await api.favourites.add(reference);
      } catch (error) {
        update(wasSaved);
        if (error instanceof ApiError && error.status === 401) setSaved(null);
        throw error;
      }
    },
    [saved, pathname, router],
  );

  const value = useMemo(() => ({ saved, toggle }), [saved, toggle]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useFavourites(): FavouritesContext | null {
  return useContext(Context);
}
