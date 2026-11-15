import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { Building2, History, Search, Sparkles, UserRound } from "lucide-react";

import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useHealth } from "@/hooks/useHealth";
import { cn } from "@/lib/utils";

export const NAV_ITEMS = [
  { to: "/match", label: "I tuoi match", icon: Sparkles },
  { to: "/ricerche", label: "Ricerche", icon: Search },
  { to: "/aziende", label: "Aziende", icon: Building2 },
  { to: "/profilo", label: "Profilo", icon: UserRound },
  { to: "/storico", label: "Storico", icon: History },
] as const;

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
  const { user } = useCurrentUser();
  const health = useHealth();
  const { pathname } = useLocation();
  const mobileNav = useRef<HTMLElement>(null);

  // Sul telefono il menu scorre in orizzontale: la voce attiva va tenuta in vista.
  useEffect(() => {
    const active = mobileNav.current?.querySelector<HTMLElement>('[aria-current="page"]');
    active?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [pathname]);

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
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto border-t border-line px-2 pt-4 text-xs text-ink-faint">
          <div className="truncate font-medium text-ink-soft">{user ? user.name : "Nessun profilo"}</div>
          <div className="mt-1 font-mono">LLM: {health.data?.llm_primary ?? "…"}</div>
        </div>
      </aside>

      {/* Barra in alto (telefono e tablet stretti) */}
      <header className="sticky top-0 z-30 border-b border-line bg-surface md:hidden">
        <div className="flex items-center justify-between px-4 pt-3">
          <Logo />
          <span className="max-w-[45%] truncate text-xs text-ink-faint">{user?.name ?? ""}</span>
        </div>
        <nav
          ref={mobileNav}
          aria-label="Sezioni principali"
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
            </NavLink>
          ))}
        </nav>
      </header>

      <main id="contenuto" className="min-h-screen min-w-0 px-4 py-6 sm:px-6 md:p-12">
        <Outlet />
      </main>
    </div>
  );
}
