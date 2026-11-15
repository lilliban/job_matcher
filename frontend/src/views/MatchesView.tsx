import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUpRight, RotateCw, X } from "lucide-react";

import { ApiError } from "@/api/client";
import { useFeedMatches, type FeedMatch } from "@/api/queries";
import { EmptyState, Hint, Loading, PageHeader } from "@/components/Page";
import { DocumentsLens } from "@/components/illustrations";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { cn } from "@/lib/utils";

const CATEGORY_LABEL: Record<string, string> = {
  analytics_ai: "Dati e AI",
  consulting_security: "Consulenza e sicurezza",
  software: "Sviluppo software",
  support_qa: "Supporto e QA",
  unclassified: "Altri ruoli",
};

type SortMode = "default" | "coverage_desc" | "coverage_asc";

const SORT_LABEL: Record<SortMode, string> = {
  default: "Ordine consigliato",
  coverage_desc: "Copertura: dalla più alta",
  coverage_asc: "Copertura: dalla più bassa",
};

// Valori di FeedMatch.region che non sono un codice paese
const REGION_REMOTE_EU = "remote_eu";
const REGION_UNKNOWN = "unknown";
const NO_COUNTRY_LABEL = "Paese non indicato";
const PAGE_SIZE = 30;
const CARD_SKILLS = 4;

const regionNames =
  typeof Intl !== "undefined" && "DisplayNames" in Intl
    ? new Intl.DisplayNames(["it"], { type: "region" })
    : null;

function countryName(code: string): string {
  try {
    return regionNames?.of(code.toUpperCase()) ?? code;
  } catch {
    return code;
  }
}

/** Etichetta del luogo: paese, "Remoto in Europa" o "Paese non indicato". */
function regionLabel(region: string): string {
  if (region === REGION_UNKNOWN) return NO_COUNTRY_LABEL;
  if (region === REGION_REMOTE_EU) return "Remoto in Europa";
  return countryName(region);
}

/** Nel menu: prima i paesi in ordine alfabetico, poi remoto, poi non indicato. */
function regionRank(region: string): number {
  if (region === REGION_UNKNOWN) return 2;
  if (region === REGION_REMOTE_EU) return 1;
  return 0;
}

function seenLabel(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("it-IT", { day: "numeric", month: "short", year: "numeric" });
}

/** Ordina per copertura; gli annunci senza copertura misurata restano in fondo. */
function byCoverage(a: FeedMatch, b: FeedMatch, direction: 1 | -1): number {
  if (a.coverage == null && b.coverage == null) return 0;
  if (a.coverage == null) return 1;
  if (b.coverage == null) return -1;
  return (a.coverage - b.coverage) * direction;
}

function coveragePct(m: FeedMatch): number | null {
  return m.coverage == null ? null : Math.round(m.coverage * 100);
}

export function MatchesView() {
  const { userId, isBooting } = useCurrentUser();
  const feed = useFeedMatches(userId);

  const [priority, setPriority] = useState<number | null>(null);
  const [country, setCountry] = useState<string>("");
  const [sort, setSort] = useState<SortMode>("default");
  const [showThesis, setShowThesis] = useState(false);
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [open, setOpen] = useState<FeedMatch | null>(null);

  const all = useMemo(() => feed.data ?? [], [feed.data]);
  const thesisCount = useMemo(() => all.filter((m) => m.kind === "thesis").length, [all]);
  // Tesi e dottorati non sono candidature da lavoro: restano fuori finché
  // non si accende il filtro. Conteggi e menu si calcolano su questa lista.
  const matches = useMemo(
    () => (showThesis ? all : all.filter((m) => m.kind !== "thesis")),
    [all, showThesis],
  );

  const priorities = useMemo(() => {
    const counts = new Map<number, { count: number; category: string }>();
    for (const m of matches) {
      const entry = counts.get(m.priority);
      if (entry) entry.count += 1;
      else counts.set(m.priority, { count: 1, category: m.category });
    }
    return [...counts.entries()].sort(([a], [b]) => a - b);
  }, [matches]);

  const countries = useMemo(() => {
    const counts = new Map<string, number>();
    for (const m of matches) counts.set(m.region, (counts.get(m.region) ?? 0) + 1);
    return [...counts.entries()]
      .map(([code, count]) => ({ code, count, name: regionLabel(code) }))
      .sort(
        (a, b) => regionRank(a.code) - regionRank(b.code) || a.name.localeCompare(b.name, "it"),
      );
  }, [matches]);

  // Un filtro rimasto su un valore che non c'è più (per esempio dopo aver
  // spento "Tesi e dottorati") vale come "nessun filtro".
  const activeCountry = countries.some((c) => c.code === country) ? country : "";
  const activePriority = priorities.some(([p]) => p === priority) ? priority : null;

  const filtered = useMemo(() => {
    const list = matches.filter(
      (m) =>
        (activePriority == null || m.priority === activePriority) &&
        (activeCountry === "" || m.region === activeCountry),
    );
    // "default" è l'ordine del server: priorità, sopra soglia, copertura
    if (sort === "coverage_desc") return [...list].sort((a, b) => byCoverage(a, b, -1));
    if (sort === "coverage_asc") return [...list].sort((a, b) => byCoverage(a, b, 1));
    return list;
  }, [matches, activePriority, activeCountry, sort]);

  const belowCount = useMemo(() => filtered.filter((m) => m.below_threshold).length, [filtered]);
  const hasFilters = activePriority != null || activeCountry !== "";

  // Ogni cambio di filtro o ordine riparte dalla prima pagina.
  const changePriority = (p: number | null) => { setPriority(p); setVisible(PAGE_SIZE); };
  const changeCountry = (c: string) => { setCountry(c); setVisible(PAGE_SIZE); };
  const changeSort = (s: SortMode) => { setSort(s); setVisible(PAGE_SIZE); };
  const toggleThesis = () => { setShowThesis((v) => !v); setVisible(PAGE_SIZE); };
  const resetFilters = () => { setPriority(null); setCountry(""); setVisible(PAGE_SIZE); };

  if (isBooting) return <Shell><Loading /></Shell>;

  if (!userId) {
    return (
      <Shell>
        <Hint className="mt-8">Crea prima il tuo profilo: i match si calcolano dalle tue competenze.</Hint>
      </Shell>
    );
  }

  if (feed.isLoading) {
    return (
      <Shell>
        <EmptyState status className="mt-8" art={<DocumentsLens className="w-full" />}>
          Carico i tuoi match… La prima volta scarico il feed, ci vuole qualche secondo.
        </EmptyState>
      </Shell>
    );
  }

  if (feed.isError) {
    const message =
      feed.error instanceof ApiError ? feed.error.message : "Non riesco a contattare il server.";
    return (
      <Shell>
        <div
          role="alert"
          className="mt-8 flex flex-col items-start gap-4 rounded-2xl border border-bad/30 bg-bad-wash p-5 text-bad sm:flex-row sm:items-center sm:justify-between"
        >
          <p className="text-[15px] leading-snug">{message}</p>
          <button
            type="button"
            onClick={() => feed.refetch()}
            disabled={feed.isFetching}
            className="jm-press inline-flex h-11 w-full shrink-0 items-center justify-center gap-2 rounded-full bg-bad px-5 text-sm font-medium text-paper-2 hover:bg-bad/90 disabled:opacity-70 sm:h-10 sm:w-auto"
          >
            <RotateCw className={cn("h-4 w-4", feed.isFetching && "animate-spin")} aria-hidden />
            Riprova
          </button>
        </div>
      </Shell>
    );
  }

  if (all.length === 0) {
    return (
      <Shell>
        <EmptyState className="mt-8" art={<DocumentsLens className="w-full" />}>
          <span className="text-ink">
            Nessun match per ora. Aggiungi le tue competenze nel{" "}
            <Link to="/profilo" className="font-medium underline underline-offset-4">
              profilo
            </Link>
            : il confronto parte da lì.
          </span>
        </EmptyState>
      </Shell>
    );
  }

  const shown = filtered.slice(0, visible);

  return (
    <Shell
      lead={`${matches.length.toLocaleString("it-IT")} annunci confrontati con le tue competenze. La percentuale dice quante delle skill richieste hai già.`}
    >
      <section
        aria-label="Filtri"
        className="mt-6 flex flex-wrap items-end gap-x-3 gap-y-3 border-y border-line py-3"
      >
        <FilterSelect
          label="Priorità"
          value={activePriority == null ? "" : String(activePriority)}
          onChange={(v) => changePriority(v === "" ? null : Number(v))}
        >
          <option value="">Tutte ({matches.length})</option>
          {priorities.map(([p, { count, category }]) => (
            <option key={p} value={p}>
              {p} · {CATEGORY_LABEL[category] ?? category} ({count})
            </option>
          ))}
        </FilterSelect>
        <FilterSelect label="Paese" value={activeCountry} onChange={changeCountry}>
          <option value="">Tutti i paesi ({matches.length})</option>
          {countries.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name} ({c.count})
            </option>
          ))}
        </FilterSelect>
        <FilterSelect label="Ordine" value={sort} onChange={(v) => changeSort(v as SortMode)}>
          {(Object.keys(SORT_LABEL) as SortMode[]).map((s) => (
            <option key={s} value={s}>
              {SORT_LABEL[s]}
            </option>
          ))}
        </FilterSelect>
        {thesisCount > 0 && (
          <button
            type="button"
            aria-pressed={showThesis}
            onClick={toggleThesis}
            className={cn(
              "jm-press inline-flex h-11 items-center gap-2 rounded-full border px-4 text-sm font-medium sm:h-10",
              showThesis
                ? "border-accent bg-accent text-paper-2"
                : "border-line-hard bg-paper-2 text-ink hover:border-accent",
            )}
          >
            Tesi e dottorati
            <span className="font-mono text-xs opacity-80">{thesisCount}</span>
          </button>
        )}
      </section>

      {filtered.length === 0 ? (
        <div className="mt-8 flex flex-col items-start gap-4">
          <EmptyState art={<DocumentsLens className="w-full" />}>Nessun annuncio con questi filtri.</EmptyState>
          <button
            type="button"
            onClick={resetFilters}
            className="jm-press inline-flex h-11 items-center rounded-full border border-line-hard bg-paper-2 px-5 text-sm font-medium hover:border-accent sm:h-10"
          >
            Azzera i filtri
          </button>
        </div>
      ) : (
        <>
          <p className="mt-4 text-sm text-ink-faint" aria-live="polite">
            {hasFilters
              ? `${filtered.length.toLocaleString("it-IT")} annunci con questi filtri`
              : `${filtered.length.toLocaleString("it-IT")} annunci`}
            {belowCount > 0 && ` · ${belowCount.toLocaleString("it-IT")} sotto soglia`}
          </p>

          <ul className="mt-3 grid grid-cols-1 items-start gap-3 md:grid-cols-2 2xl:grid-cols-3">
            {shown.map((m, i) => (
              <li key={`${m.source_url ?? ""}|${m.title ?? ""}|${m.company_name ?? ""}|${i}`} className="min-w-0">
                <MatchCard m={m} onOpen={() => setOpen(m)} />
              </li>
            ))}
          </ul>

          {filtered.length > visible && (
            <div className="mt-8 flex flex-col items-center gap-2">
              <button
                type="button"
                onClick={() => setVisible((v) => v + PAGE_SIZE)}
                className="jm-press inline-flex h-11 w-full items-center justify-center rounded-full border border-line-hard bg-paper-2 px-6 text-sm font-medium hover:border-accent sm:w-auto"
              >
                Mostra altri {Math.min(PAGE_SIZE, filtered.length - visible)}
              </button>
              <span className="font-mono text-xs text-ink-faint">
                {shown.length} di {filtered.length.toLocaleString("it-IT")}
              </span>
            </div>
          )}
        </>
      )}

      <MatchDetailSheet m={open} onClose={() => setOpen(null)} />
    </Shell>
  );
}

/* -------------------------------------------------------------------------- */
/* Struttura della pagina                                                      */
/* -------------------------------------------------------------------------- */

function Shell({ lead, children }: { lead?: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="I tuoi match" lead={lead} />
      {children}
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="flex min-w-0 flex-1 basis-40 flex-col gap-1 sm:flex-none sm:basis-auto">
      <span className="text-xs font-medium text-ink-faint">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 w-full min-w-0 rounded-full border border-field bg-paper-2 px-4 text-sm text-ink hover:border-accent sm:h-10 sm:w-56"
      >
        {children}
      </select>
    </label>
  );
}

/* -------------------------------------------------------------------------- */
/* Scheda compatta di un match                                                 */
/* -------------------------------------------------------------------------- */

function CoverageBar({ m, size = "sm" }: { m: FeedMatch; size?: "sm" | "lg" }) {
  const pct = coveragePct(m);
  if (pct == null) return <p className="text-xs text-ink-faint">Copertura non misurabile</p>;
  return (
    <div className="flex items-center gap-3">
      <div
        role="progressbar"
        aria-label="Copertura delle skill richieste"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={`${pct}%`}
        className={cn("flex-1 overflow-hidden rounded-full bg-accent-wash", size === "lg" ? "h-2.5" : "h-1.5")}
      >
        {pct > 0 && (
          <div
            className={cn("jm-bar-fill h-full rounded-full", m.below_threshold ? "bg-warn" : "bg-accent")}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      <span
        className={cn(
          "shrink-0 font-mono leading-none tracking-[-0.02em] tabular-nums",
          size === "lg" ? "text-3xl" : "text-lg",
        )}
      >
        {pct}%
      </span>
    </div>
  );
}

/** Sotto questa soglia di skill misurate la percentuale dice poco (vedi pipeline.py). */
const LOW_DATA_SKILLS = 3;

function isLowData(m: FeedMatch): boolean {
  return m.coverage != null && m.skills_measured < LOW_DATA_SKILLS;
}

/** "1 di 1 skill": su quante skill dell'annuncio è calcolata la percentuale. */
function skillsBasis(m: FeedMatch): string {
  return `${m.matched_skills.length} di ${m.skills_measured} skill`;
}

function LowDataTag() {
  return (
    <span
      className="rounded-full border border-dashed border-line-hard px-2 py-0.5 text-xs font-medium text-ink-soft"
      title="La percentuale è calcolata su meno di 3 skill dell'annuncio"
    >
      Pochi dati
    </span>
  );
}

function BelowTag() {
  return (
    <span className="rounded-full bg-warn-wash px-2 py-0.5 text-xs font-medium text-warn">Sotto soglia</span>
  );
}

/** Colonna in alto a destra della card: percentuale, barra corta, etichette. */
function CardScore({ m }: { m: FeedMatch }) {
  const pct = coveragePct(m);
  if (pct == null) {
    return (
      <div className="w-24 shrink-0 text-right">
        <span className="font-mono text-lg leading-none text-ink-faint">—</span>
        <p className="mt-1 text-xs text-ink-faint">non misurabile</p>
      </div>
    );
  }
  const low = isLowData(m);
  return (
    <div className="flex w-24 shrink-0 flex-col items-end gap-1.5">
      <span className="font-mono text-xl leading-none tracking-[-0.02em] tabular-nums">{pct}%</span>
      <div
        role="progressbar"
        aria-label="Copertura delle skill richieste"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-valuetext={low ? `${pct}%, calcolata su ${skillsBasis(m)}` : `${pct}%`}
        className="h-1.5 w-full overflow-hidden rounded-full bg-accent-wash"
      >
        {pct > 0 && (
          <div
            className={cn("jm-bar-fill h-full rounded-full", m.below_threshold ? "bg-warn" : "bg-accent")}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
      {low && <span className="font-mono text-xs text-ink-soft">{skillsBasis(m)}</span>}
      {low && <LowDataTag />}
      {m.below_threshold && <BelowTag />}
    </div>
  );
}

function MatchCard({ m, onOpen }: { m: FeedMatch; onOpen: () => void }) {
  const skills = m.matched_skills.slice(0, CARD_SKILLS);
  const extra = m.matched_skills.length - skills.length;
  const place = regionLabel(m.region);

  return (
    <article className="group relative flex flex-col rounded-2xl border border-line bg-paper-2 p-4 transition-colors hover:border-line-hard">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px] font-medium leading-snug tracking-[-0.01em] [overflow-wrap:anywhere]">
            {/* Il pulsante copre tutta la card: un clic ovunque apre il dettaglio */}
            <button
              type="button"
              onClick={onOpen}
              className="text-left after:absolute after:inset-0 after:rounded-2xl after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-accent"
            >
              {m.title ?? "Annuncio senza titolo"}
            </button>
          </h2>
          <p className="mt-0.5 text-sm text-ink-soft [overflow-wrap:anywhere]">
            {m.company_name ?? "Azienda non indicata"} · {place}
            {m.kind === "thesis" && " · Tesi o dottorato"}
          </p>
          {skills.length > 0 && (
            <ul className="mt-2.5 flex flex-wrap gap-1.5" aria-label="Skill che hai">
              {skills.map((s) => (
                <li key={s} className="rounded-full bg-good-wash px-2.5 py-1 font-mono text-xs text-good">
                  {s}
                </li>
              ))}
              {extra > 0 && <li className="px-1 py-1 font-mono text-xs text-ink-faint">+{extra}</li>}
            </ul>
          )}
        </div>
        <CardScore m={m} />
      </div>

      <div className="flex items-center justify-between gap-3 pt-3">
        <span className="text-xs text-ink-faint">Priorità {m.priority}</span>
        {m.source_url && (
          <a
            href={m.source_url}
            target="_blank"
            rel="noreferrer"
            aria-label={`Apri l'annuncio ${m.title ?? ""} in una nuova scheda`}
            className="jm-press relative z-10 inline-flex h-10 items-center gap-1 rounded-full bg-accent px-4 text-sm font-medium text-paper-2 hover:bg-accent-ink"
          >
            Apri
            <ArrowUpRight className="h-4 w-4" aria-hidden />
          </a>
        )}
      </div>
    </article>
  );
}

/* -------------------------------------------------------------------------- */
/* Dettaglio completo (pannello laterale)                                      */
/* -------------------------------------------------------------------------- */

function MatchDetailSheet({ m, onClose }: { m: FeedMatch | null; onClose: () => void }) {
  const seen = m ? seenLabel(m.first_seen_at) : null;
  return (
    <Dialog.Root open={!!m} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-ink/30" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col overflow-y-auto border-l border-line bg-paper p-5 font-sans text-ink focus:outline-none sm:p-8"
        >
          {m && (
            <>
              <div className="flex items-start justify-between gap-4">
                <p className="text-sm text-ink-faint">
                  Priorità {m.priority} · {CATEGORY_LABEL[m.category] ?? m.category}
                </p>
                <Dialog.Close
                  aria-label="Chiudi dettaglio"
                  className="jm-press -mr-2 -mt-2 grid h-11 w-11 shrink-0 place-items-center rounded-full text-ink-soft hover:bg-surface"
                >
                  <X className="h-5 w-5" aria-hidden />
                </Dialog.Close>
              </div>
              <Dialog.Title className="mt-1 text-2xl font-medium leading-tight tracking-[-0.02em] [overflow-wrap:anywhere]">
                {m.title ?? "Annuncio senza titolo"}
              </Dialog.Title>
              <p className="mt-1 text-[15px] text-ink-soft">
                {m.company_name ?? "Azienda non indicata"} · {regionLabel(m.region)}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {m.kind === "thesis" && (
                  <span className="rounded-full border border-line-hard px-2.5 py-1 text-xs font-medium text-ink-soft">
                    Tesi o dottorato
                  </span>
                )}
                {m.below_threshold && <BelowTag />}
                {isLowData(m) && <LowDataTag />}
              </div>

              <div className="mt-6">
                <p className="mb-2 text-xs font-medium text-ink-faint">Copertura delle skill richieste</p>
                <CoverageBar m={m} size="lg" />
                {isLowData(m) && (
                  <p className="mt-2 text-sm text-ink-soft">
                    Calcolata su {skillsBasis(m)}: con così pochi dati la percentuale è indicativa.
                  </p>
                )}
              </div>

              <dl className="mt-6 space-y-4">
                <SkillRow label="Hai" skills={m.matched_skills} tone="have" />
                <SkillRow label="Ti mancano" skills={m.missing_required} tone="missing" />
                <SkillRow label="Gradite, non le hai" skills={m.missing_nice} tone="nice" />
              </dl>

              <div className="mt-auto flex flex-col gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
                <span className="font-mono text-xs text-ink-faint">{seen ? `Visto il ${seen}` : ""}</span>
                {m.source_url && (
                  <a
                    href={m.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="jm-press inline-flex h-11 items-center justify-center gap-1.5 rounded-full bg-accent px-5 text-sm font-medium text-paper-2 hover:bg-accent-ink"
                  >
                    Apri l'annuncio
                    <ArrowUpRight className="h-4 w-4" aria-hidden />
                  </a>
                )}
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

const SKILL_TONE = {
  have: "border-transparent bg-good-wash text-good",
  missing: "border-line-hard text-ink",
  nice: "border-dashed border-line-hard text-ink-soft",
} as const;

function SkillRow({
  label,
  skills,
  tone,
}: {
  label: string;
  skills: string[];
  tone: keyof typeof SKILL_TONE;
}) {
  if (skills.length === 0) return null;
  return (
    <div>
      <dt className="mb-1.5 text-xs font-medium text-ink-faint">
        {label} <span className="font-mono">({skills.length})</span>
      </dt>
      <dd className="flex flex-wrap gap-1.5">
        {skills.map((s) => (
          <span key={s} className={cn("rounded-full border px-2.5 py-1 font-mono text-xs", SKILL_TONE[tone])}>
            {s}
          </span>
        ))}
      </dd>
    </div>
  );
}
