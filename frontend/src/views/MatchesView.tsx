import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, RotateCw } from "lucide-react";

import { ApiError } from "@/api/client";
import { useFeedMatches, type FeedMatch } from "@/api/queries";
import { Guide } from "@/components/Avatar";
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

export function MatchesView() {
  const { userId, isBooting } = useCurrentUser();
  const feed = useFeedMatches(userId);

  const [priority, setPriority] = useState<number | null>(null);
  const [country, setCountry] = useState<string>("");
  const [sort, setSort] = useState<SortMode>("default");
  const [showThesis, setShowThesis] = useState(false);
  const [visible, setVisible] = useState(PAGE_SIZE);

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

  if (isBooting) return <Shell><Notice>Caricamento…</Notice></Shell>;

  if (!userId) {
    return (
      <Shell>
        <div className="mt-10">
          <Guide>Crea prima il tuo profilo: i match si calcolano dalle tue competenze.</Guide>
        </div>
      </Shell>
    );
  }

  if (feed.isLoading) {
    return (
      <Shell>
        <Notice>Carico i tuoi match… La prima volta scarico il feed, ci vuole qualche secondo.</Notice>
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
          className="mt-10 flex flex-col items-start gap-4 rounded-2xl border border-bad/30 bg-bad-wash p-5 text-bad sm:flex-row sm:items-center sm:justify-between sm:p-6"
        >
          <p className="text-[15px] leading-snug">{message}</p>
          <button
            type="button"
            onClick={() => feed.refetch()}
            disabled={feed.isFetching}
            className="jm-press inline-flex h-11 w-full shrink-0 items-center justify-center gap-2 rounded-full bg-bad px-5 text-sm font-medium text-white hover:bg-bad/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-bad/50 disabled:opacity-60 sm:h-9 sm:w-auto"
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
        <div className="mt-10">
          <Guide>
            Nessun match per ora. Aggiungi le tue competenze nel{" "}
            <Link to="/profile" className="font-medium underline underline-offset-4">
              profilo
            </Link>
            : il confronto parte da lì.
          </Guide>
        </div>
      </Shell>
    );
  }

  const shown = filtered.slice(0, visible);

  return (
    <Shell
      lead={`${matches.length.toLocaleString("it-IT")} annunci confrontati con le tue competenze. La copertura dice quante delle skill richieste hai già.`}
    >
      <section
        aria-label="Filtri"
        className="mt-8 flex flex-col gap-5 border-y border-line py-5 xl:flex-row xl:items-end xl:justify-between"
      >
        <div className="min-w-0">
          <FilterLabel id="filtro-priorita">Priorità</FilterLabel>
          <div role="group" aria-labelledby="filtro-priorita" className="mt-2 flex flex-wrap gap-2">
            <Chip active={activePriority == null} onClick={() => changePriority(null)}>
              Tutte
              <ChipCount>{matches.length}</ChipCount>
            </Chip>
            {priorities.map(([p, { count, category }]) => (
              <Chip key={p} active={activePriority === p} onClick={() => changePriority(p)}>
                <span className="font-mono text-xs opacity-70">{p}</span>
                {CATEGORY_LABEL[category] ?? category}
                <ChipCount>{count}</ChipCount>
              </Chip>
            ))}
          </div>

          {thesisCount > 0 && (
            <div className="mt-4">
              <FilterLabel id="filtro-tipo">Mostra anche</FilterLabel>
              <div role="group" aria-labelledby="filtro-tipo" className="mt-2 flex flex-wrap gap-2">
                <Chip active={showThesis} onClick={toggleThesis}>
                  Tesi e dottorati
                  <ChipCount>{thesisCount}</ChipCount>
                </Chip>
              </div>
            </div>
          )}
        </div>

        <div className="grid shrink-0 grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block">
            <FilterLabel>Paese</FilterLabel>
            <Select value={activeCountry} onChange={changeCountry}>
              <option value="">Tutti i paesi ({matches.length})</option>
              {countries.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.name} ({c.count})
                </option>
              ))}
            </Select>
          </label>
          <label className="block">
            <FilterLabel>Ordine</FilterLabel>
            <Select value={sort} onChange={(v) => changeSort(v as SortMode)}>
              {(Object.keys(SORT_LABEL) as SortMode[]).map((s) => (
                <option key={s} value={s}>
                  {SORT_LABEL[s]}
                </option>
              ))}
            </Select>
          </label>
        </div>
      </section>

      {filtered.length === 0 ? (
        <div className="mt-10 flex flex-col items-start gap-4">
          <p className="text-ink-soft">Nessun annuncio con questi filtri.</p>
          <button
            type="button"
            onClick={resetFilters}
            className="jm-press inline-flex h-11 items-center rounded-full border border-line-hard bg-paper-2 px-5 text-sm font-medium hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 sm:h-9"
          >
            Azzera i filtri
          </button>
        </div>
      ) : (
        <>
          <p className="mt-5 text-sm text-ink-faint" aria-live="polite">
            {hasFilters
              ? `${filtered.length.toLocaleString("it-IT")} annunci con questi filtri`
              : `${filtered.length.toLocaleString("it-IT")} annunci`}
            {belowCount > 0 && ` · ${belowCount.toLocaleString("it-IT")} sotto soglia`}
          </p>

          <ul className="mt-4 grid grid-cols-1 gap-4 2xl:grid-cols-2">
            {shown.map((m, i) => (
              <li key={`${m.source_url ?? ""}|${m.title ?? ""}|${m.company_name ?? ""}|${i}`} className="min-w-0">
                <MatchCard m={m} />
              </li>
            ))}
          </ul>

          {filtered.length > visible && (
            <div className="mt-8 flex flex-col items-center gap-2">
              <button
                type="button"
                onClick={() => setVisible((v) => v + PAGE_SIZE)}
                className="jm-press inline-flex h-11 w-full items-center justify-center rounded-full border border-line-hard bg-paper-2 px-6 text-sm font-medium hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 sm:w-auto"
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
    </Shell>
  );
}

/* -------------------------------------------------------------------------- */
/* Struttura della pagina                                                      */
/* -------------------------------------------------------------------------- */

function Shell({ lead, children }: { lead?: string; children: ReactNode }) {
  return (
    // I margini negativi annullano il padding di <main>: la pagina stende il
    // proprio fondo fino ai bordi e riapplica lo stesso padding.
    <div className="jm-matches -m-6 min-h-screen bg-paper p-6 font-sans text-ink md:-m-12 md:p-12">
      <div className="mx-auto max-w-6xl">
        <header>
          <h1 className="text-4xl font-medium leading-[1.05] tracking-[-0.03em] [font-stretch:96%] sm:text-5xl">
            I tuoi match
          </h1>
          {lead && <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-ink-soft">{lead}</p>}
        </header>
        {children}
      </div>
    </div>
  );
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <p role="status" className="mt-10 text-ink-soft">
      {children}
    </p>
  );
}

function FilterLabel({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <span id={id} className="block text-xs font-medium text-ink-faint">
      {children}
    </span>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "jm-press inline-flex h-11 items-center gap-2 rounded-full border px-4 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 sm:h-9",
        active
          ? "border-accent bg-accent text-paper"
          : "border-line-hard bg-paper-2 text-ink hover:border-accent",
      )}
    >
      {children}
    </button>
  );
}

function ChipCount({ children }: { children: ReactNode }) {
  return <span className="font-mono text-xs opacity-70">{children}</span>;
}

function Select({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="mt-2 block h-11 w-full min-w-0 rounded-full border border-line-hard bg-paper-2 px-4 text-sm text-ink hover:border-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 sm:h-9 sm:min-w-52"
    >
      {children}
    </select>
  );
}

/* -------------------------------------------------------------------------- */
/* Scheda di un match                                                          */
/* -------------------------------------------------------------------------- */

function MatchCard({ m }: { m: FeedMatch }) {
  const pct = m.coverage == null ? null : Math.round(m.coverage * 100);
  const seen = seenLabel(m.first_seen_at);
  const unknownCountry = m.region === REGION_UNKNOWN;

  return (
    <article className="flex h-full flex-col rounded-2xl border border-line bg-paper-2 p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <p className="font-mono text-xs text-ink-faint">
          Priorità {m.priority} · {CATEGORY_LABEL[m.category] ?? m.category}
        </p>
        {m.kind === "thesis" && (
          <span className="rounded-full border border-line-hard px-2.5 py-1 text-xs font-medium text-ink-soft">
            Tesi o dottorato
          </span>
        )}
        {m.below_threshold && (
          <span className="ml-auto rounded-full bg-warn-wash px-2.5 py-1 text-xs font-medium text-warn">
            Sotto soglia
          </span>
        )}
      </div>

      <h2 className="mt-3 text-xl font-medium leading-snug tracking-[-0.015em] [overflow-wrap:anywhere]">
        {m.title ?? "Annuncio senza titolo"}
      </h2>
      <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[15px] text-ink-soft [overflow-wrap:anywhere]">
        <span>
          {m.company_name ?? "Azienda non indicata"}
          {!unknownCountry && ` · ${regionLabel(m.region)}`}
        </span>
        {unknownCountry && (
          <span className="rounded-full border border-dashed border-line-hard px-2 py-0.5 text-xs text-ink-faint">
            {NO_COUNTRY_LABEL}
          </span>
        )}
      </p>

      {pct == null ? (
        // Niente barra e niente riquadro: senza skill riconosciute nel testo
        // (o senza testo nel feed) basta dirlo sottovoce.
        <p className="mt-4 text-xs text-ink-faint">Copertura non misurabile</p>
      ) : (
        <>
          <div className="mt-5">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-xs font-medium text-ink-faint">Copertura</span>
              <span className="font-mono text-2xl leading-none tracking-[-0.02em]">{pct}%</span>
            </div>
            <div
              role="progressbar"
              aria-label="Copertura delle skill richieste"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
              aria-valuetext={`${pct}%`}
              className="mt-2 h-2 overflow-hidden rounded-full bg-accent-wash"
            >
              {pct > 0 && (
                <div
                  className={cn("jm-bar-fill h-full rounded-full", m.below_threshold ? "bg-warn" : "bg-accent")}
                  style={{ width: `${pct}%` }}
                />
              )}
            </div>
          </div>

          <dl className="mt-5 space-y-3">
            <SkillRow label="Hai" skills={m.matched_skills} tone="have" />
            <SkillRow label="Ti mancano" skills={m.missing_required} tone="missing" />
            <SkillRow label="Gradite, non le hai" skills={m.missing_nice} tone="nice" />
          </dl>
        </>
      )}

      <div className="mt-auto flex flex-col gap-3 pt-6 sm:flex-row sm:items-center sm:justify-between">
        <span className="font-mono text-xs text-ink-faint">{seen ? `Visto il ${seen}` : ""}</span>
        {m.source_url && (
          <a
            href={m.source_url}
            target="_blank"
            rel="noreferrer"
            className="jm-press group inline-flex h-11 w-full items-center justify-center gap-1.5 rounded-full bg-accent px-5 text-sm font-medium text-paper hover:bg-accent-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:ring-offset-2 sm:h-9 sm:w-auto"
          >
            Apri l'annuncio
            <ArrowUpRight
              className="h-4 w-4 transition-transform duration-150 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transition-none"
              aria-hidden
            />
          </a>
        )}
      </div>
    </article>
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
    <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-[9.5rem_minmax(0,1fr)] sm:gap-3">
      <dt className="pt-1 text-xs font-medium text-ink-faint">{label}</dt>
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
