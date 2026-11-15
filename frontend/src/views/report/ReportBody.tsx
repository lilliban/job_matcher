import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useIntelligenceReport } from "@/api/queries";
import type { IntelligenceReportOut } from "@/api/schemas";

/** Analisi di una ricerca: com'è andata e cosa ti blocca. */
export function ReportPanel({ userId, sessionId }: { userId: string; sessionId: string }) {
  const report = useIntelligenceReport(userId, sessionId);
  if (report.isLoading) return <Card className="p-5 text-ink-soft sm:p-8">Calcolo l'analisi…</Card>;
  if (!report.data) return <Card className="p-5 text-ink-soft sm:p-8">Nessun dato ancora.</Card>;
  return <ReportBody data={report.data} />;
}

function ReportBody({ data }: { data: IntelligenceReportOut }) {
  return (
    <>
      {data.summary && (
        <Card className="p-5 sm:p-8">
          <p className="mb-2 text-xs font-medium text-ink-faint">
            In poche parole
          </p>
          <p className="text-xl leading-snug tracking-[-0.01em]">{data.summary}</p>
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
          <Card className="p-5 sm:p-8">
            <h2 className="mb-4 jm-h2">Cosa ti manca più spesso</h2>
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
        <Card className="p-5 sm:p-8">
          <h2 className="mb-4 jm-h2">Aziende target: cosa è successo</h2>
          <ul className="space-y-3">
            {data.company_outcomes!.map((c) => (
              <li
                key={c.company}
                className="rounded-xl border border-line bg-paper-2 p-3 text-sm"
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
        <Card className="p-5 sm:p-8">
          <h2 className="mb-4 jm-h2">Prova anche questi ruoli</h2>
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
      <div className="text-xs font-medium text-ink-faint">
        {label}
      </div>
      <div className="mt-1 font-mono text-2xl tracking-[-0.02em] tabular-nums">{value ?? "—"}</div>
    </Card>
  );
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${Math.round(n * 100)}%`;
}
