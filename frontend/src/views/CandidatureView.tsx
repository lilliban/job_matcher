import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FileText } from "lucide-react";

import { ApiError } from "@/api/client";
import { useTrackedMatches, type TrackedGroup, type TrackedMatch } from "@/api/queries";
import { EmptyState, Hint, Loading, PageHeader } from "@/components/Page";
import { FolderTabs } from "@/components/illustrations";
import { MatchDetailSheet } from "@/components/match/MatchDetailSheet";
import { StatusMenu } from "@/components/match/StatusMenu";
import { dateLabel, fromMatch, regionLabel, skillsBasis, coveragePct } from "@/components/match/matchModel";
import { useMatchActions } from "@/components/match/useMatchActions";
import { useCurrentUser } from "@/hooks/useCurrentUser";

const DOC_LABEL: Record<string, string> = {
  cv: "CV",
  cover_letter: "Lettera",
  email: "Email",
};

/** Candidature: tutto ciò che hai salvato o inviato, in un solo posto, diviso per stato. */
export function CandidatureView() {
  const { userId, isBooting } = useCurrentUser();
  const tracked = useTrackedMatches(userId);
  const { setStatus } = useMatchActions();
  const [openId, setOpenId] = useState<string | null>(null);

  const groups = useMemo(() => tracked.data ?? [], [tracked.data]);
  const total = useMemo(() => groups.reduce((n, g) => n + g.count, 0), [groups]);
  const filled = groups.filter((g) => g.count > 0);

  const openItem = useMemo(() => {
    if (!openId) return null;
    for (const g of groups) {
      const hit = g.items.find((i) => i.id === openId);
      if (hit) return hit;
    }
    return null;
  }, [groups, openId]);

  const lead = total
    ? "Gli annunci che hai salvato e le candidature in corso, divisi per stato. Il menu di ogni riga ne cambia lo stato."
    : "Gli annunci che salvi e le candidature che mandi, divisi per stato.";

  const shell = (children: React.ReactNode) => (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Candidature" lead={lead} />
      <div className="mt-8">{children}</div>
    </div>
  );

  if (isBooting || tracked.isLoading) return shell(<Loading>Carico le tue candidature…</Loading>);

  if (!userId) {
    return shell(<Hint>Crea prima il tuo profilo: poi qui trovi le candidature.</Hint>);
  }

  if (tracked.isError) {
    const message =
      tracked.error instanceof ApiError ? tracked.error.message : "Non riesco a contattare il server.";
    return shell(
      <div role="alert" className="rounded-2xl border border-bad/30 bg-bad-wash p-5 text-[15px] text-bad">
        {message}
      </div>,
    );
  }

  if (total === 0) {
    return shell(
      <EmptyState art={<FolderTabs className="w-full" />}>
        <span className="text-ink">
          Nessuna candidatura per ora. Apri un annuncio in{" "}
          <Link to="/match" className="font-medium underline underline-offset-4">
            I tuoi match
          </Link>{" "}
          e premi «Salva»: lo ritrovi qui, con i documenti e lo stato.
        </span>
      </EmptyState>,
    );
  }

  return shell(
    <>
      <div className="space-y-10">
        {filled.map((g) => (
          <Group key={g.status} group={g} onOpen={setOpenId} onStatus={(item, next) => void setStatus(fromMatch(item), next)} />
        ))}
      </div>
      <MatchDetailSheet view={openItem ? fromMatch(openItem) : null} onClose={() => setOpenId(null)} />
    </>,
  );
}

function Group({
  group,
  onOpen,
  onStatus,
}: {
  group: TrackedGroup;
  onOpen: (id: string) => void;
  onStatus: (item: TrackedMatch, next: string) => void;
}) {
  const headingId = `gruppo-${group.status}`;
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="jm-h2 flex items-baseline gap-2">
        {group.label}
        <span className="font-mono text-sm font-normal text-ink-faint">{group.count}</span>
      </h2>
      <ul className="mt-3 divide-y divide-line overflow-hidden rounded-2xl border border-line bg-paper-2">
        {group.items.map((item) => (
          <Row key={item.id} item={item} onOpen={() => onOpen(item.id)} onStatus={(next) => onStatus(item, next)} />
        ))}
      </ul>
    </section>
  );
}

function Row({
  item,
  onOpen,
  onStatus,
}: {
  item: TrackedMatch;
  onOpen: () => void;
  onStatus: (next: string) => void;
}) {
  const view = fromMatch(item);
  const pct = coveragePct(view);
  const date = dateLabel(item.created_at);

  return (
    <li className="group relative grid gap-3 p-4 transition-colors hover:bg-paper sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-6">
      <div className="min-w-0">
        <h3 className="text-base font-medium leading-snug tracking-[-0.01em] [overflow-wrap:anywhere]">
          {/* Come nelle card del feed: il titolo è l'unico punto di arresto della riga, con il menu dello stato */}
          <button
            type="button"
            onClick={onOpen}
            className="jm-stretch text-left after:absolute after:inset-0 after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-inset focus-visible:after:ring-accent"
          >
            {view.title}
          </button>
        </h3>
        <p className="mt-0.5 text-sm text-ink-soft [overflow-wrap:anywhere]">
          {[view.company ?? "Azienda non indicata", regionLabel(view.region), date].filter(Boolean).join(" · ")}
        </p>
        <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Documenti generati">
          {item.documents.length === 0 ? (
            <li className="text-xs text-ink-soft">Nessun documento ancora</li>
          ) : (
            item.documents.map((d) => (
              <li
                key={d.id}
                className="inline-flex items-center gap-1 rounded-full bg-surface px-2.5 py-1 text-xs font-medium text-ink-soft"
              >
                <FileText className="h-3.5 w-3.5" aria-hidden />
                {DOC_LABEL[d.doc_type] ?? "Documento"}
              </li>
            ))
          )}
        </ul>
      </div>

      <div className="flex items-center justify-between gap-4 sm:justify-end">
        <div className="text-left sm:text-right">
          {pct == null ? (
            <p className="text-xs text-ink-soft">Skill non trovate</p>
          ) : (
            <>
              <p className="font-mono text-lg leading-none tabular-nums">{pct}%</p>
              <p className="mt-1 font-mono text-xs text-ink-soft">{skillsBasis(view)}</p>
            </>
          )}
        </div>
        <StatusMenu
          value={item.status}
          onChange={onStatus}
          caption={null}
          label={`Stato della candidatura: ${view.title}`}
          className="relative z-10 w-40 shrink-0"
        />
      </div>
    </li>
  );
}
