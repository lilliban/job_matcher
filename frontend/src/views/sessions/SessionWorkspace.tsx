import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyBox } from "@/components/illustrations";
import { Card } from "@/components/ui/card";
import {
  useCancelSession,
  useSession,
  useSessionListings,
  useSessionLogs,
  useSessionMatches,
  useSessionStatus,
  useStartSession,
  type SavedMatch,
} from "@/api/queries";
import { MatchDetailSheet } from "@/components/match/MatchDetailSheet";
import { LowDataTag, StatusTag } from "@/components/match/parts";
import { coveragePct, fromMatch, isLowData, regionLabel, skillsBasis } from "@/components/match/matchModel";
import { ReportPanel } from "../report/ReportBody";

const RUN_STATE_LABEL: Record<string, string> = {
  draft: "Pronta",
  running: "In esecuzione",
  completed: "Completata",
  error: "Non riuscita",
  cancelled: "Annullata",
};

const MODE_LABEL: Record<string, string> = {
  companies: "Nelle mie aziende",
  market: "Su tutte le aziende",
  both: "Aziende e mercato",
};

const STATUS_FILTERS = [
  { key: "", label: "Tutti" },
  { key: "new", label: "Nuovi" },
  { key: "saved", label: "Salvati" },
  { key: "applied", label: "Inviati" },
  { key: "interview", label: "Colloquio" },
  { key: "rejected", label: "Rifiutati" },
];

export function SessionWorkspace({
  userId,
  sessionId,
  onDelete,
}: {
  userId: string;
  sessionId: string;
  onDelete?: () => void;
}) {
  const session = useSession(userId, sessionId);
  const status = useSessionStatus(userId, sessionId);
  const logs = useSessionLogs(userId, sessionId, status.data?.status === "running");
  const listings = useSessionListings(userId, sessionId);
  const matches = useSessionMatches(userId, sessionId);
  const startSession = useStartSession(userId);
  const cancelSession = useCancelSession(userId);

  const [tab, setTab] = useState<"matches" | "analysis">("matches");
  const [filter, setFilter] = useState<string>("");
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);

  const runStatus = status.data?.status ?? session.data?.status ?? "draft";
  const isRunning = runStatus === "running";
  const isTerminal = ["completed", "error", "cancelled"].includes(runStatus);

  const filteredMatches = useMemo(() => {
    const all = matches.data ?? [];
    if (!filter) return all;
    return all.filter((m) => m.status === filter);
  }, [matches.data, filter]);

  // Il dettaglio si ricalcola dai dati più recenti: cambiando stato l'etichetta si aggiorna da sola
  const selectedMatch = useMemo(() => {
    if (!selectedMatchId) return null;
    return matches.data?.find((m) => m.id === selectedMatchId) ?? null;
  }, [selectedMatchId, matches.data]);

  // I match sono già in ordine: prima i legati al profilo, poi «Poco legati al tuo profilo»
  const { related, unrelated } = useMemo(() => {
    return {
      related: filteredMatches.filter((m) => !m.off_profile),
      unrelated: filteredMatches.filter((m) => m.off_profile),
    };
  }, [filteredMatches]);

  async function handleRun() {
    try {
      await startSession.mutateAsync(sessionId);
      toast.success("Ricerca avviata");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore avvio");
    }
  }

  async function handleCancel() {
    try {
      await cancelSession.mutateAsync(sessionId);
      toast.message("Sto fermando la ricerca. Si chiude tra poco.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Errore annullamento");
    }
  }

  if (session.isLoading) return <div className="text-ink-faint">Carico la ricerca…</div>;
  if (!session.data)
    return <div className="text-ink-faint">Ricerca non trovata.</div>;

  const s = session.data;
  const progress =
    status.data?.progress_total && status.data.progress_total > 0
      ? Math.round(((status.data.progress_current ?? 0) / status.data.progress_total) * 100)
      : 0;

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium text-ink-faint">
              {MODE_LABEL[s.search_mode ?? "both"] ?? "Ricerca"}
            </p>
            <h2 className="jm-h2">{s.role_title || "Qualsiasi ruolo adatto a te"}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-soft">
              {s.preferred_country && <span>{s.preferred_country}</span>}
              {s.location_pref && <span>· {s.location_pref}</span>}
              {s.contract_type && <span>· {s.contract_type}</span>}
              <span>· pertinenza minima {Math.round((s.match_threshold ?? 0) * 100)}%</span>
              <span className={runStatus === "error" ? "text-bad" : undefined}>
                · {RUN_STATE_LABEL[runStatus] ?? runStatus}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {onDelete && !isRunning && (
              <Button variant="ghost" onClick={onDelete}>
                Elimina
              </Button>
            )}
            {isRunning ? (
              <Button variant="outline" onClick={handleCancel} disabled={cancelSession.isPending}>
                Annulla ricerca
              </Button>
            ) : (
              <Button onClick={handleRun} disabled={startSession.isPending}>
                {isTerminal ? "Rilancia" : "Avvia ricerca"}
              </Button>
            )}
          </div>
        </div>

        {(isRunning || status.data?.progress_message) && (
          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-xs text-ink-soft">
              <span>{status.data?.progress_message ?? "—"}</span>
              <span className="font-mono">
                {status.data?.matches_found ?? 0} match · {progress}%
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
              <div
                className="h-full bg-accent transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {(logs.data ?? []).length > 0 && (
          <details className="mt-4">
            <summary className="flex min-h-10 cursor-pointer items-center text-sm text-ink-soft">
              Dettagli tecnici ({logs.data!.length})
            </summary>
            <div className="mt-2 max-h-56 overflow-y-auto rounded-xl border border-line bg-surface p-3 font-mono text-xs text-ink-soft">
              {logs.data!.slice(-100).map((l, i) => {
                const line = [l.source, l.action, l.result].filter(Boolean).join(" · ");
                return (
                  <div key={i} className="mb-1">
                    <span className="text-ink-faint">
                      {new Date(l.ts).toLocaleTimeString("it-IT")}
                    </span>{" "}
                    <span
                      className={
                        l.level === "error"
                          ? "text-bad"
                          : l.level === "warning"
                            ? "text-warn"
                            : "text-ink-soft"
                      }
                    >
                      {line || "…"}
                    </span>
                  </div>
                );
              })}
            </div>
          </details>
        )}
      </Card>

      <div role="tablist" aria-label="Sezioni della ricerca" className="flex gap-1 border-b border-line">
        {([["matches", "Annunci trovati"], ["analysis", "Com'è andata"]] as const).map(([k, label]) => (
          <button
            key={k}
            type="button"
            role="tab"
            aria-selected={tab === k}
            onClick={() => setTab(k)}
            className={
              "-mb-px h-11 border-b-2 px-4 text-sm transition-colors " +
              (tab === k ? "border-accent font-medium text-ink" : "border-transparent text-ink-soft hover:text-ink")
            }
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "analysis" && <ReportPanel userId={userId} sessionId={sessionId} />}

      {tab === "matches" && (
      <Card className="p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="jm-h2">Annunci raccolti</h2>
            <p className="text-sm text-ink-soft">
              {listings.data?.length ?? 0} annunci · {matches.data?.length ?? 0} match
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.key)}
                aria-pressed={filter === f.key}
                className={
                  "jm-press inline-flex h-10 items-center rounded-full px-4 text-sm " +
                  (filter === f.key
                    ? "bg-accent text-paper-2"
                    : "text-ink-soft hover:bg-surface")
                }
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {filteredMatches.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-line-hard px-6 py-6 text-center text-sm text-ink-soft">
            <EmptyBox className="w-24 sm:w-28" />
            Nessun annuncio sopra soglia, per ora. Se la ricerca è finita guarda «Com'è andata» per capire perché.
          </div>
        ) : (
          <>
            <p className="mb-3 text-sm text-ink-soft">
              La percentuale è la copertura delle tue skill, la stessa di «I tuoi match». Il punteggio della
              ricerca, la «Pertinenza», lo trovi nel dettaglio di ogni annuncio.
            </p>
            <MatchList matches={related} onOpen={setSelectedMatchId} />
            {unrelated.length > 0 && (
              <section aria-labelledby="poco-legati" className={related.length > 0 ? "mt-8" : undefined}>
                <h3 id="poco-legati" className="text-base font-medium">
                  Poco legati al tuo profilo{" "}
                  <span className="font-mono text-sm font-normal text-ink-faint">{unrelated.length}</span>
                </h3>
                <p className="mb-3 mt-1 text-sm text-ink-soft">
                  Il ruolo non è tra quelli del tuo profilo, o nessuna delle tue skill compare nell'annuncio. Li
                  tengo qui, in fondo, nel caso ti interessino.
                </p>
                <MatchList matches={unrelated} onOpen={setSelectedMatchId} />
              </section>
            )}
          </>
        )}
      </Card>
      )}

      <MatchDetailSheet
        view={selectedMatch ? fromMatch(selectedMatch) : null}
        onClose={() => setSelectedMatchId(null)}
      />
    </div>
  );
}

/** Una riga per annuncio: titolo che apre il dettaglio, copertura, stato. */
function MatchList({ matches, onOpen }: { matches: SavedMatch[]; onOpen: (id: string) => void }) {
  if (matches.length === 0) return null;
  return (
    <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-paper-2">
      {matches.map((m) => {
        const view = fromMatch(m);
        const pct = coveragePct(view);
        return (
          <li
            key={m.id}
            className="group relative flex items-start justify-between gap-4 p-4 transition-colors hover:bg-paper"
          >
            <div className="min-w-0">
              <h4 className="text-[15px] font-medium leading-snug [overflow-wrap:anywhere]">
                <button
                  type="button"
                  onClick={() => onOpen(m.id)}
                  className="jm-stretch text-left after:absolute after:inset-0 after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-accent"
                >
                  {view.title}
                </button>
              </h4>
              <p className="mt-0.5 text-sm text-ink-soft [overflow-wrap:anywhere]">
                {[view.company, view.region !== "unknown" ? regionLabel(view.region) : null]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              {m.status !== "new" && (
                <div className="mt-2">
                  <StatusTag status={m.status} />
                </div>
              )}
            </div>
            <div className="shrink-0 text-right">
              {pct == null ? (
                <p className="max-w-24 text-xs leading-snug text-ink-soft">Skill non trovate nell'annuncio</p>
              ) : (
                <>
                  <p className="font-mono text-lg leading-none tabular-nums">{pct}%</p>
                  <p className="mt-1 font-mono text-xs text-ink-soft">{skillsBasis(view)}</p>
                  {isLowData(view) && (
                    <div className="mt-1">
                      <LowDataTag />
                    </div>
                  )}
                </>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
