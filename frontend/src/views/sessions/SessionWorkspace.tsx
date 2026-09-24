import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
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
  error: "Errore",
  cancelled: "Annullata",
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
}: {
  userId: string;
  sessionId: string;
}) {
  const session = useSession(userId, sessionId);
  const status = useSessionStatus(userId, sessionId);
  const logs = useSessionLogs(userId, sessionId, status.data?.status === "running");
  const listings = useSessionListings(userId, sessionId);
  const matches = useSessionMatches(userId, sessionId);
  const startSession = useStartSession(userId);
  const cancelSession = useCancelSession(userId);
  const updateStatus = useUpdateMatchStatus();

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
            <p className="font-mono text-xs uppercase tracking-wider text-ink-faint">
              Ricerca
            </p>
            <h2 className="font-serif text-2xl">{s.role_title}</h2>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-ink-soft">
              {s.preferred_country && <span>{s.preferred_country}</span>}
              {s.location_pref && <span>· {s.location_pref}</span>}
              {s.contract_type && <span>· {s.contract_type}</span>}
              <span>· soglia {Math.round((s.match_threshold ?? 0) * 100)}%</span>
              <Badge variant={isRunning ? "warn" : isTerminal ? "good" : "outline"}>
                {RUN_STATE_LABEL[runStatus] ?? runStatus}
              </Badge>
            </div>
          </div>
          <div className="flex gap-2">
            {isRunning ? (
              <Button variant="destructive" onClick={handleCancel} disabled={cancelSession.isPending}>
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
            <summary className="cursor-pointer text-xs uppercase tracking-wider text-ink-faint">
              Log live ({logs.data!.length})
            </summary>
            <div className="mt-2 max-h-56 overflow-y-auto rounded-sm border border-line bg-ink p-3 font-mono text-xs text-paper/80">
              {logs.data!.slice(-100).map((l, i) => {
                const line = [l.source, l.action, l.result].filter(Boolean).join(" · ");
                return (
                  <div key={i} className="mb-1">
                    <span className="text-paper/40">
                      {new Date(l.ts).toLocaleTimeString("it-IT")}
                    </span>{" "}
                    <span
                      className={
                        l.level === "error"
                          ? "text-bad"
                          : l.level === "warning"
                            ? "text-warn"
                            : "text-paper/80"
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

      <Card className="p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-serif text-2xl">Annunci raccolti</h2>
            <p className="text-sm text-ink-soft">
              {listings.data?.length ?? 0} annunci · {matches.data?.length ?? 0} match
              sopra soglia
            </p>
          </div>
          <div className="flex gap-1">
            {STATUS_FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => setFilter(f.key)}
                className={
                  "rounded-sm px-3 py-1 text-xs transition-colors " +
                  (filter === f.key
                    ? "bg-ink text-paper"
                    : "text-ink-soft hover:bg-line/50")
                }
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {filteredMatches.length === 0 ? (
          <div className="rounded border border-dashed border-line p-8 text-center text-sm text-ink-faint">
            Nessun match ancora. Avvia la ricerca per vederli.
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
                      "w-full rounded-sm border p-3 text-left text-sm transition-colors " +
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
                        {m.status}
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
                <div className="rounded border border-dashed border-line p-8 text-sm text-ink-faint">
                  Seleziona un annuncio a sinistra per vedere dettagli e documenti.
                </div>
              )}
            </div>
          </div>
        )}
      </Card>
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
          <p className="font-mono text-xs uppercase tracking-wider text-ink-faint">
            {listing?.source_board ?? "—"}
          </p>
          <h3 className="font-serif text-xl">{listing?.title ?? "—"}</h3>
          <p className="text-sm text-ink-soft">{listing?.company_name}</p>
        </div>
        <div className="text-right">
          <div className="font-serif text-3xl text-accent">
            {Math.round((match.score ?? 0) * 100)}%
          </div>
          <select
            value={match.status}
            onChange={(e) => onStatusChange(e.target.value)}
            className="mt-2 h-7 rounded-sm border border-line bg-paper-2 px-2 text-xs"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
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
            <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-faint">
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
            <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-faint">
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
        <div className="rounded border border-line bg-paper p-3 text-sm text-ink-soft">
          {match.gap_analysis}
        </div>
      )}

      {listing?.description && (
        <details>
          <summary className="cursor-pointer text-xs uppercase tracking-wider text-ink-faint">
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
