import { useState } from "react";

import { Guide } from "@/components/Avatar";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { ApplyPanel } from "./ApplyView";
import { SearchWizard } from "./sessions/SearchWizard";

type Tab = "search" | "link";

const TABS: Array<{ key: Tab; label: string; hint: string }> = [
  { key: "search", label: "Cerca per me", hint: "Trovo gli annunci giusti per il tuo profilo" },
  { key: "link", label: "Da un link", hint: "Hai già un annuncio: preparo CV e lettera" },
];

export function SessionsView() {
  const { userId, isBooting } = useCurrentUser();
  const [tab, setTab] = useState<Tab>("search");

  if (isBooting) return <div className="text-ink-faint">Caricamento…</div>;

  if (!userId) {
    return (
      <div className="mx-auto max-w-3xl">
        <Guide>Prima creiamo il tuo profilo, poi partiamo con le ricerche.</Guide>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div
        role="tablist"
        aria-label="Cosa vuoi fare"
        className="grid grid-cols-1 gap-2 rounded border border-line bg-paper-2 p-1.5 sm:grid-cols-2"
      >
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={
              "rounded-sm px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 " +
              (tab === t.key ? "bg-ink text-paper" : "hover:bg-paper")
            }
          >
            <span className="block text-sm font-medium">{t.label}</span>
            <span className={"block text-xs " + (tab === t.key ? "text-paper/70" : "text-ink-faint")}>
              {t.hint}
            </span>
          </button>
        ))}
      </div>

      {tab === "search" ? <SearchWizard userId={userId} /> : <ApplyPanel />}
    </div>
  );
}
