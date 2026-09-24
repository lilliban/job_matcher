import { NavLink, Outlet } from "react-router-dom";

import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useHealth } from "@/hooks/useHealth";

const NAV_ITEMS = [
  { to: "/profile", num: "01", label: "Profilo" },
  { to: "/collections", num: "02", label: "Aziende" },
  { to: "/sessions", num: "03", label: "Ricerche" },
  { to: "/intelligence", num: "04", label: "Resoconto" },
];

export function AppLayout() {
  const { user } = useCurrentUser();
  const health = useHealth();

  return (
    <div className="grid min-h-screen grid-cols-1 md:grid-cols-[232px_1fr] bg-paper text-ink">
      <aside className="hidden md:flex flex-col bg-ink text-paper py-8 px-6 sticky top-0 h-screen">
        <div className="mb-10 flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-sm bg-paper text-ink font-serif text-lg font-semibold">
            JM
          </div>
          <span className="font-serif text-lg tracking-tight">JOBMATCHER</span>
        </div>

        <nav className="flex flex-1 flex-col gap-1" aria-label="Sezioni principali">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              data-view={item.to.replace("/", "")}
              className={({ isActive }) =>
                [
                  "rail-item flex items-baseline gap-3 rounded-sm px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "is-active bg-paper/10 text-paper"
                    : "text-paper/70 hover:bg-paper/5 hover:text-paper",
                ].join(" ")
              }
            >
              <span className="font-mono text-xs opacity-60">{item.num}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto pt-6 text-xs opacity-60">
          <div>{user ? user.name : "Nessun profilo"}</div>
          <div className="mt-1 font-mono">
            LLM: {health.data?.llm_primary ?? "…"}
          </div>
        </div>
      </aside>

      <main className="min-h-screen overflow-x-hidden p-6 md:p-12">
        <Outlet />
      </main>
    </div>
  );
}
