import { useState } from "react";
import { Link2, Search } from "lucide-react";

import { Hint, Loading, PageHeader } from "@/components/Page";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { cn } from "@/lib/utils";
import { ApplyPanel } from "./ApplyView";
import { SearchWizard } from "./sessions/SearchWizard";

type Tab = "search" | "link";

const TABS: Array<{ key: Tab; label: string; hint: string; icon: typeof Search }> = [
  { key: "search", label: "Cerca per me", hint: "Trovo gli annunci giusti per il tuo profilo", icon: Search },
  { key: "link", label: "Da un link", hint: "Hai già un annuncio: preparo CV e lettera", icon: Link2 },
];

/** Ricerche: qui si lancia una nuova ricerca. Le ricerche passate sono in Storico. */
export function SessionsView() {
  const { userId, isBooting } = useCurrentUser();
  const [tab, setTab] = useState<Tab>("search");

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Ricerche"
        lead="Lancia una nuova ricerca di annunci. Quelle già fatte le trovi in Storico."
      />

      {isBooting ? (
        <Loading />
      ) : !userId ? (
        <Hint>Prima crea il tuo profilo, poi parti con le ricerche.</Hint>
      ) : (
        <>
          <div
            role="tablist"
            aria-label="Cosa vuoi fare"
            className="grid grid-cols-1 gap-1.5 rounded-2xl bg-surface p-1.5 sm:grid-cols-2"
          >
            {TABS.map((t) => {
              const active = tab === t.key;
              const Icon = t.icon;
              return (
                <button
                  key={t.key}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setTab(t.key)}
                  className={cn(
                    "jm-press flex min-h-14 items-center gap-3 rounded-xl px-4 py-3 text-left",
                    active
                      ? "bg-accent text-paper-2"
                      : "text-ink hover:bg-paper-2",
                  )}
                >
                  <Icon className="h-5 w-5 shrink-0" aria-hidden />
                  <span>
                    <span className="block text-[15px] font-medium">{t.label}</span>
                    <span className={cn("block text-xs", active ? "text-paper-2/85" : "text-ink-faint")}>
                      {t.hint}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>

          {tab === "search" ? <SearchWizard userId={userId} /> : <ApplyPanel />}
        </>
      )}
    </div>
  );
}
