import { useEffect } from "react";
import { toast } from "sonner";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useIntelligenceReport, useSessions } from "@/api/queries";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useAppState } from "@/stores/useAppState";
import type { IntelligenceReportOut } from "@/api/schemas";

const Header = () => (
  <header className="mb-8">
    <p className="mb-2 font-mono text-xs uppercase tracking-widest text-ink-faint">
      Passo quattro
    </p>
    <h1 className="font-serif text-5xl leading-none">Perché è andata così</h1>
    <p className="mt-4 max-w-2xl text-ink-soft">
      Zero match non significa zero informazioni. Qui c'è cosa ho fatto, cosa ho
      trovato, e cosa ti blocca.
    </p>
  </header>
);

export function IntelligenceView() {
  const { userId, isBooting } = useCurrentUser();
  const sessionId = useAppState((s) => s.sessionId);
  const setSessionId = useAppState((s) => s.setSessionId);

  const sessionsQuery = useSessions(userId);
  const report = useIntelligenceReport(userId, sessionId);

  // Auto-select prima sessione se non c'è una selezione valida.
  useEffect(() => {
    if (!sessionId && sessionsQuery.data && sessionsQuery.data.length > 0) {
      setSessionId(sessionsQuery.data[0].id);
    }
  }, [sessionId, sessionsQuery.data, setSessionId]);

  useEffect(() => {
    if (report.error) toast.error(report.error.message);
  }, [report.error]);

  if (isBooting) return <div className="text-ink-faint">Caricamento…</div>;

  if (!userId) {
    return (
      <div className="mx-auto max-w-3xl">
        <Header />
        <Card className="p-8 text-ink-soft">
          Crea prima il tuo profilo e almeno una ricerca.
        </Card>
      </div>
    );
  }

  if ((sessionsQuery.data ?? []).length === 0) {
    return (
      <div className="mx-auto max-w-3xl">
        <Header />
        <Card className="p-8 text-ink-soft">Nessuna ricerca ancora avviata.</Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <Header />

      <Card className="flex flex-wrap items-center gap-3 p-4">
        <label className="font-mono text-xs uppercase tracking-wider text-ink-faint">
          Ricerca passata ({(sessionsQuery.data ?? []).length})
        </label>
        <select
          value={sessionId ?? ""}
          onChange={(e) => setSessionId(e.target.value)}
          className="h-10 flex-1 min-w-[16rem] rounded-sm border border-line bg-paper-2 px-3 text-sm font-medium"
        >
          {(sessionsQuery.data ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.role_title} · {new Date(s.created_at).toLocaleDateString("it-IT")}
            </option>
          ))}
        </select>
        {(sessionsQuery.data ?? []).length > 1 && (
          <span className="text-xs text-ink-faint">
            Tutte le tue ricerche restano qui, seleziona per confrontarle
          </span>
        )}
      </Card>

      {report.isLoading ? (
        <Card className="p-8 text-ink-faint">Calcolo il resoconto…</Card>
      ) : report.data ? (
        <ReportBody data={report.data} />
      ) : (
        <Card className="p-8 text-ink-faint">Nessun dato ancora.</Card>
      )}
    </div>
  );
}

function ReportBody({ data }: { data: IntelligenceReportOut }) {
  return (
    <>
      {data.summary && (
        <Card className="p-8">
          <p className="mb-2 font-mono text-xs uppercase tracking-wider text-ink-faint">
            In poche parole
          </p>
          <p className="font-serif text-2xl leading-snug">{data.summary}</p>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Metric label="Annunci esaminati" value={data.total_listings} />
        <Metric label="Match sopra soglia" value={data.total_matches} />
        <Metric label="Score medio" value={fmtPct(data.avg_score)} />
        <Metric label="Miglior match" value={fmtPct(data.best_score)} />
        <Metric label="Portali usati" value={data.sources_queried ?? "—"} />
        <Metric label="Aziende verificate" value={data.companies_verified ?? "—"} />
      </div>

      {(() => {
        const missing = (data.top_missing_skills ?? []) as Array<{
          name?: string;
          count?: number;
        }>;
        return missing.length > 0 ? (
          <Card className="p-8">
            <h2 className="mb-4 font-serif text-2xl">Cosa ti manca più spesso</h2>
            <ul className="space-y-2">
              {missing.map((s, i) => (
                <li
                  key={s.name ?? i}
                  className="flex items-center justify-between text-sm"
                >
                  <span>{s.name ?? "—"}</span>
                  <span className="text-ink-faint">{s.count ?? 0} annunci</span>
                </li>
              ))}
            </ul>
          </Card>
        ) : null;
      })()}

      {(data.company_outcomes ?? []).length > 0 && (
        <Card className="p-8">
          <h2 className="mb-4 font-serif text-2xl">Aziende target: cosa è successo</h2>
          <ul className="space-y-3">
            {data.company_outcomes!.map((c) => (
              <li
                key={c.company}
                className="rounded-sm border border-line bg-paper-2 p-3 text-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{c.company}</span>
                  <Badge variant={c.matches_found ? "good" : "outline"}>
                    {c.matches_found ?? 0} match
                  </Badge>
                </div>
                {c.reason && <p className="mt-1 text-ink-soft">{c.reason}</p>}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {(data.alternative_roles ?? []).length > 0 && (
        <Card className="p-8">
          <h2 className="mb-4 font-serif text-2xl">Prova anche questi ruoli</h2>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {data.alternative_roles!.map((r) => (
              <Card key={r.role} className="p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{r.role}</span>
                  {r.overlap && <Badge variant="default">{r.overlap}</Badge>}
                </div>
                {r.why && <p className="mt-2 text-sm text-ink-soft">{r.why}</p>}
              </Card>
            ))}
          </div>
        </Card>
      )}
    </>
  );
}

function Metric({ label, value }: { label: string; value: string | number | null }) {
  return (
    <Card className="p-4">
      <div className="font-mono text-xs uppercase tracking-wider text-ink-faint">
        {label}
      </div>
      <div className="mt-1 font-serif text-2xl">{value ?? "—"}</div>
    </Card>
  );
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${Math.round(n * 100)}%`;
}
