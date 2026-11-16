import { useSearchParams } from "react-router-dom";
import { History, Link2, Search } from "lucide-react";

import { Hint, Loading, PageHeader } from "@/components/Page";
import { SearchListings } from "@/components/illustrations";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { cn } from "@/lib/utils";
import { ApplyPanel } from "./ApplyView";
import { SearchHistory } from "./ReportView";
import { SearchWizard } from "./sessions/SearchWizard";

/** Valore di ?scheda= nell'indirizzo: il link «Prepara CV e lettera» e il vecchio /storico atterrano qui. */
type Tab = "ricerca" | "link" | "storico";

const TABS: Array<{ key: Tab; label: string; hint: string; icon: typeof Search }> = [
  { key: "ricerca", label: "Cerca per me", hint: "Trovo gli annunci giusti per il tuo profilo", icon: Search },
  { key: "link", label: "Da un link", hint: "Hai già un annuncio: preparo CV e lettera", icon: Link2 },
  { key: "storico", label: "Ricerche fatte", hint: "Rivedi cosa hanno trovato", icon: History },
];

function parseTab(value: string | null): Tab {
  return value === "link" || value === "storico" ? value : "ricerca";
}

/**
 * Ricerche: lanciare una ricerca, preparare i documenti da un link, rivedere le
 * ricerche già fatte. Lo stato di una candidatura si gestisce in Candidature.
 */
export function SessionsView() {
  const { userId, isBooting } = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const tab = parseTab(params.get("scheda"));
  // Il link e la candidatura arrivano dal pulsante «Prepara CV e lettera» di un annuncio
  const initialUrl = params.get("url") ?? "";
  const matchId = params.get("match") ?? undefined;

  const selectTab = (next: Tab) => {
    // cambiare scheda a mano lascia cadere l'annuncio con cui si era arrivati
    setParams(next === "ricerca" ? {} : { scheda: next }, { replace: true });
  };

  return (
    <div className={cn("mx-auto space-y-6", tab === "storico" ? "max-w-6xl" : "max-w-3xl")}>
      <PageHeader
        title="Ricerche"
        lead="Cerca annunci nuovi, prepara CV e lettera da un link o rivedi le ricerche già fatte."
        art={<SearchListings className="w-full" />}
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
            className="grid grid-cols-1 gap-1.5 rounded-2xl bg-surface p-1.5 sm:grid-cols-3"
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
                  onClick={() => selectTab(t.key)}
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

          {tab === "ricerca" && <SearchWizard userId={userId} />}
          {tab === "link" && <ApplyPanel key={matchId ?? initialUrl} initialUrl={initialUrl} matchId={matchId} />}
          {tab === "storico" && <SearchHistory />}
        </>
      )}
    </div>
  );
}
