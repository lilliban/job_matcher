import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Building2, FolderOpen, Search, Sparkles, UserRound } from "lucide-react";

import { useNewMatchCount } from "@/api/queries";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { cn } from "@/lib/utils";

export const NAV_ITEMS = [
  { to: "/match", label: "I tuoi match", icon: Sparkles },
  { to: "/candidature", label: "Candidature", icon: FolderOpen },
  { to: "/ricerche", label: "Ricerche", icon: Search },
  { to: "/aziende", label: "Aziende", icon: Building2 },
  { to: "/profilo", label: "Profilo", icon: UserRound },
] as const;

/** Quanti annunci nuovi da ieri: il numero accanto a «I tuoi match». Niente se sono zero. */
function NewBadge({ count, active }: { count: number | undefined; active: boolean }) {
  if (!count) return null;
  return (
    <>
      <span
        aria-hidden
        className={cn(
          "ml-auto grid h-5 min-w-5 place-items-center rounded-full px-1.5 font-mono text-xs leading-none tabular-nums",
          active ? "bg-paper-2 text-accent" : "bg-accent text-paper-2",
        )}
      >
        {count > 99 ? "99+" : count}
      </span>
      <span className="sr-only">, {count} nuovi da ieri</span>
    </>
  );
}

/** Marchio: monogramma JM su teal, stesso alfabeto della pagina. */
function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <span
        aria-hidden
        className="grid h-9 w-9 place-items-center rounded-xl bg-accent font-mono text-sm font-medium tracking-[-0.04em] text-paper-2"
      >
        JM
      </span>
      <span className="text-[17px] font-semibold tracking-[-0.02em] text-ink">JobMatcher</span>
    </span>
  );
}

export function AppLayout() {
  const { user, userId } = useCurrentUser();
  const newCount = useNewMatchCount(userId);
  const { pathname } = useLocation();
  const mobileNav = useRef<HTMLElement>(null);
  // Sfumatura a destra finché il menu ha ancora voci nascoste da quel lato.
  const [moreRight, setMoreRight] = useState(false);

  const updateMoreRight = useCallback(() => {
    const nav = mobileNav.current;
    if (!nav) return;
    setMoreRight(nav.scrollLeft + nav.clientWidth < nav.scrollWidth - 4);
  }, []);

  // Sul telefono il menu scorre in orizzontale: la voce attiva va tenuta in vista.
  useEffect(() => {
    const active = mobileNav.current?.querySelector<HTMLElement>('[aria-current="page"]');
    active?.scrollIntoView({ block: "nearest", inline: "center" });
    updateMoreRight();
  }, [pathname, updateMoreRight]);

  useEffect(() => {
    window.addEventListener("resize", updateMoreRight);
    return () => window.removeEventListener("resize", updateMoreRight);
  }, [updateMoreRight]);

  return (
    <div className="grid min-h-screen grid-cols-1 bg-paper text-ink md:grid-cols-[240px_minmax(0,1fr)]">
      <a
        href="#contenuto"
        className="sr-only z-50 rounded-full bg-accent px-4 py-2 text-paper-2 focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Vai al contenuto
      </a>

      {/* Barra laterale (desktop) */}
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line bg-surface px-4 py-6 md:flex">
        <div className="mb-8 px-2">
          <Logo />
        </div>

        <nav className="flex flex-1 flex-col gap-1" aria-label="Sezioni principali">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "jm-press flex h-11 items-center gap-3 rounded-full px-3.5 text-[15px] font-medium",
                  isActive
                    ? "bg-accent text-paper-2"
                    : "text-ink-soft hover:bg-paper-2 hover:text-ink",
                )
              }
            >
              <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden />
              {label}
              {to === "/match" && <NewBadge count={newCount} active={pathname.startsWith("/match")} />}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto border-t border-line px-2 pt-4 text-xs text-ink-faint">
          <div className="truncate font-medium text-ink-soft">{user ? user.name : "Nessun profilo"}</div>
        </div>
      </aside>

      {/* Barra in alto (telefono e tablet stretti) */}
      <header className="sticky top-0 z-30 border-b border-line bg-surface md:hidden">
        <div className="flex items-center justify-between px-4 pt-3">
          <Logo />
          <span className="max-w-[45%] truncate text-xs text-ink-faint">{user?.name ?? ""}</span>
        </div>
        <div className="relative">
        <nav
          ref={mobileNav}
          aria-label="Sezioni principali"
          onScroll={updateMoreRight}
          className="flex gap-1 overflow-x-auto scroll-px-3 px-3 py-2 [scrollbar-width:none]"
        >
          {NAV_ITEMS.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "jm-press flex h-11 shrink-0 items-center rounded-full px-3.5 text-sm font-medium",
                  isActive ? "bg-accent text-paper-2" : "text-ink-soft hover:bg-paper-2",
                )
              }
            >
              {label}
              {to === "/match" && (
                <span className="ml-2 inline-flex">
                  <NewBadge count={newCount} active={pathname.startsWith("/match")} />
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        {/* Indica che il menu continua a destra: sparisce a fine corsa */}
        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-surface to-transparent transition-opacity duration-150",
            moreRight ? "opacity-100" : "opacity-0",
          )}
        />
        </div>
      </header>

      <main id="contenuto" className="min-h-screen min-w-0 px-4 py-6 sm:px-6 md:p-12">
        <Outlet />
      </main>
    </div>
  );
}
