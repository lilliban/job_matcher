import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EmptyBox } from "@/components/illustrations";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  useCancelSession,
  useSession,
  useSessionListings,
  useSessionLogs,
  useSessionMatches,
  useSessionStatus,
  useStartSession,
  useUpdateMatchStatus,
} from "@/api/queries";
import { MatchDocuments } from "./MatchDocuments";
import { ReportPanel } from "../report/ReportBody";
import type { MatchDetailOut } from "@/api/schemas";

function splitSkills(raw: string | null | undefined): string[] {
  if (!raw) return [];
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

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
  both: "Aziende + mercato",
};

const MATCH_STATUS_LABEL: Record<string, string> = {
  new: "Nuovo",
  saved: "Salvato",
  applied: "Inviato",
  interview: "Colloquio",
  rejected: "Rifiutato",
  discarded: "Scartato",
};

const STATUS_FILTERS = [
  { key: "", label: "Tutti" },
  { key: "new", label: "Nuovi" },
  { key: "saved", label: "Salvati" },
  { key: "applied", label: "Inviati" },
  { key: "interview", label: "Colloquio" },
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
  const updateStatus = useUpdateMatchStatus();

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

  const selectedMatch: MatchDetailOut | null = useMemo(() => {
    if (!selectedMatchId) return null;
    return matches.data?.find((m) => m.id === selectedMatchId) ?? null;
  }, [selectedMatchId, matches.data]);

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
      toast.message("Annullamento richiesto — termina al prossimo checkpoint");
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
              <span>· soglia {Math.round((s.match_threshold ?? 0) * 100)}%</span>
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
              Log live ({logs.data!.length})
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
              sopra soglia
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.key)}
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
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,320px)_minmax(0,1fr)]">
            <ul className="space-y-2">
              {filteredMatches.map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedMatchId(m.id)}
                    className={
                      "jm-press w-full rounded-xl border p-3 text-left text-sm " +
                      (selectedMatchId === m.id
                        ? "border-accent bg-accent-wash"
                        : "border-line bg-paper-2 hover:border-line-hard")
                    }
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium">
                        {m.listing?.title ?? "—"}
                      </span>
                      <span className="font-mono text-xs text-accent">
                        {Math.round((m.score ?? 0) * 100)}%
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-between text-xs text-ink-faint">
                      <span className="truncate">{m.listing?.company_name}</span>
                      <Badge variant="outline" className="ml-2 shrink-0">
                        {MATCH_STATUS_LABEL[m.status ?? ""] ?? m.status}
                      </Badge>
                    </div>
                  </button>
                </li>
              ))}
            </ul>

            <div className="min-h-64">
              {selectedMatch ? (
                <MatchDetail
                  match={selectedMatch}
                  onStatusChange={(status) => {
                    updateStatus.mutate(
                      { matchId: selectedMatch.id, body: { status } },
                      { onSuccess: () => toast.success("Stato aggiornato") },
                    );
                  }}
                />
              ) : (
                <div className="rounded-2xl border border-dashed border-line p-8 text-sm text-ink-faint">
                  Seleziona un annuncio a sinistra per vedere dettagli e documenti.
                </div>
              )}
            </div>
          </div>
        )}
      </Card>
      )}
    </div>
  );
}

const STATUSES = ["new", "saved", "applied", "interview", "rejected", "discarded"] as const;

function MatchDetail({
  match,
  onStatusChange,
}: {
  match: MatchDetailOut;
  onStatusChange: (status: string) => void;
}) {
  const listing = match.listing;
  return (
    <Card className="space-y-4 p-6">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-ink-faint">
            {listing?.source_board ?? "—"}
          </p>
          <h3 className="jm-h2">{listing?.title ?? "—"}</h3>
          <p className="text-sm text-ink-soft">{listing?.company_name}</p>
        </div>
        <div className="text-right">
          <div className="font-mono text-3xl tracking-[-0.02em] text-accent">
            {Math.round((match.score ?? 0) * 100)}%
          </div>
          <select
            value={match.status}
            onChange={(e) => onStatusChange(e.target.value)}
            aria-label="Stato della candidatura"
            className="mt-2 h-10 rounded-full border border-field bg-paper-2 px-3 text-sm"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {MATCH_STATUS_LABEL[s] ?? s}
              </option>
            ))}
          </select>
        </div>
      </header>

      {listing?.source_url && (
        <a
          href={listing.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-accent underline-offset-4 hover:underline"
        >
          Vai all'annuncio originale ↗
        </a>
      )}

      {(() => {
        const matched = splitSkills(match.matched_skills);
        return matched.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-medium text-ink-faint">
              Match
            </p>
            <div className="flex flex-wrap gap-1">
              {matched.map((s) => (
                <Badge key={s} variant="good">
                  + {s}
                </Badge>
              ))}
            </div>
          </div>
        ) : null;
      })()}

      {(() => {
        const missing = splitSkills(match.missing_skills);
        return missing.length > 0 ? (
          <div>
            <p className="mb-2 text-xs font-medium text-ink-faint">
              Ti manca
            </p>
            <div className="flex flex-wrap gap-1">
              {missing.map((s) => (
                <Badge key={s} variant="warn">
                  − {s}
                </Badge>
              ))}
            </div>
          </div>
        ) : null;
      })()}

      {match.gap_analysis && (
        <div className="rounded-xl border border-line bg-paper p-3 text-sm text-ink-soft">
          {match.gap_analysis}
        </div>
      )}

      {listing?.description && (
        <details>
          <summary className="flex min-h-10 cursor-pointer items-center text-sm text-ink-soft">
            Descrizione annuncio
          </summary>
          <p className="mt-2 whitespace-pre-wrap text-sm text-ink-soft">
            {listing.description}
          </p>
        </details>
      )}

      <MatchDocuments matchId={match.id} />
    </Card>
  );
}
