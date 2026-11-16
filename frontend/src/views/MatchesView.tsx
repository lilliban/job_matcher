import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, RotateCw } from "lucide-react";

import { ApiError } from "@/api/client";
import { useFeedMatches, useTrackedMatches, type FeedMatch, type TrackedMatch } from "@/api/queries";
import { EmptyState, Hint, Loading, PageHeader } from "@/components/Page";
import { DocumentsLens } from "@/components/illustrations";
import { MatchDetailSheet } from "@/components/match/MatchDetailSheet";
import { CardScore, StatusTag } from "@/components/match/parts";
import {
  CATEGORY_LABEL,
  REGION_REMOTE_EU,
  REGION_UNKNOWN,
  THRESHOLD_PCT,
  fromFeed,
  isTracked,
  regionLabel,
  type MatchView,
} from "@/components/match/matchModel";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { cn } from "@/lib/utils";

type SortMode = "default" | "coverage_desc" | "coverage_asc";

const SORT_LABEL: Record<SortMode, string> = {
  default: "Ordine consigliato",
  coverage_desc: "Copertura: dalla più alta",
  coverage_asc: "Copertura: dalla più bassa",
};

const PAGE_SIZE = 30;
const CARD_SKILLS = 4;

/** Nel menu: prima i paesi in ordine alfabetico, poi remoto, poi non indicato. */
function regionRank(region: string): number {
  if (region === REGION_UNKNOWN) return 2;
  if (region === REGION_REMOTE_EU) return 1;
  return 0;
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
  const tracked = useTrackedMatches(userId);

  const [onlyNew, setOnlyNew] = useState(false);
  const [priority, setPriority] = useState<number | null>(null);
  const [country, setCountry] = useState<string>("");
  const [sort, setSort] = useState<SortMode>("default");
  const [showThesis, setShowThesis] = useState(false);
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [open, setOpen] = useState<FeedMatch | null>(null);

  const all = useMemo(() => feed.data ?? [], [feed.data]);

  // Le candidature già salvate, per indirizzo dell'annuncio: la card dice a che punto sono
  const savedByUrl = useMemo(() => {
    const map = new Map<string, TrackedMatch>();
    for (const group of tracked.data ?? []) {
      for (const item of group.items) {
        const url = item.listing?.source_url;
        if (url) map.set(url, item);
      }
    }
    return map;
  }, [tracked.data]);

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

  const newCount = useMemo(() => matches.filter((m) => m.is_new).length, [matches]);
  // A zero il filtro non ha nulla da mostrare: vale come spento.
  const activeNew = onlyNew && newCount > 0;

  const filtered = useMemo(() => {
    const list = matches.filter(
      (m) =>
        (!activeNew || m.is_new) &&
        (activePriority == null || m.priority === activePriority) &&
        (activeCountry === "" || m.region === activeCountry),
    );
    // "default" è l'ordine del server: priorità, sopra soglia, copertura
    if (sort === "coverage_desc") return [...list].sort((a, b) => byCoverage(a, b, -1));
    if (sort === "coverage_asc") return [...list].sort((a, b) => byCoverage(a, b, 1));
    return list;
  }, [matches, activeNew, activePriority, activeCountry, sort]);

  const belowCount = useMemo(() => filtered.filter((m) => m.below_threshold).length, [filtered]);
  // Il gruppo di ruoli sulla card serve solo se nella lista ce n'è più d'uno.
  const showCategory = useMemo(() => new Set(filtered.map((m) => m.category)).size > 1, [filtered]);
  const hasFilters = activeNew || activePriority != null || activeCountry !== "";

  // Ogni cambio di filtro o ordine riparte dalla prima pagina.
  const changePriority = (p: number | null) => { setPriority(p); setVisible(PAGE_SIZE); };
  const changeCountry = (c: string) => { setCountry(c); setVisible(PAGE_SIZE); };
  const changeSort = (s: SortMode) => { setSort(s); setVisible(PAGE_SIZE); };
  const toggleThesis = () => { setShowThesis((v) => !v); setVisible(PAGE_SIZE); };
  const toggleNew = () => { setOnlyNew((v) => !v); setVisible(PAGE_SIZE); };
  const resetFilters = () => { setPriority(null); setCountry(""); setOnlyNew(false); setVisible(PAGE_SIZE); };

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
          Carico i tuoi match… Scarico il feed degli annunci: ci vuole circa mezzo minuto la prima volta.
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
  // Il dettaglio si ricalcola a ogni render: appena l'annuncio viene salvato, lo stato arriva da solo.
  const openView: MatchView | null = open
    ? fromFeed(open, open.source_url ? savedByUrl.get(open.source_url) : undefined)
    : null;

  return (
    <Shell
      lead={`${matches.length.toLocaleString("it-IT")} annunci confrontati con le tue competenze. La percentuale dice quante delle skill richieste hai già.`}
      note={`Mostro anche gli annunci sotto il ${THRESHOLD_PCT}%, per non perderne di buoni.`}
    >
      <section
        aria-label="Filtri"
        className="mt-6 flex flex-wrap items-end gap-x-3 gap-y-3 border-y border-line py-3"
      >
        <FilterToggle
          pressed={activeNew}
          disabled={newCount === 0}
          onClick={toggleNew}
          count={newCount}
          title={newCount === 0 ? "Nessun annuncio nuovo da ieri" : undefined}
        >
          Nuovi da ieri
        </FilterToggle>
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
          <FilterToggle pressed={showThesis} onClick={toggleThesis} count={thesisCount}>
            Tesi e dottorati
          </FilterToggle>
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
            {belowCount > 0 && ` · ${belowCount.toLocaleString("it-IT")} sotto il ${THRESHOLD_PCT}%`}
          </p>

          <ul className="mt-3 grid grid-cols-1 items-start gap-3 md:grid-cols-2 2xl:grid-cols-3">
            {shown.map((m, i) => (
              <li key={`${m.source_url ?? ""}|${m.title ?? ""}|${m.company_name ?? ""}|${i}`} className="min-w-0">
                <MatchCard
                  m={m}
                  saved={m.source_url ? savedByUrl.get(m.source_url) : undefined}
                  showCategory={showCategory}
                  onOpen={() => setOpen(m)}
                />
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

      <MatchDetailSheet view={openView} onClose={() => setOpen(null)} />
    </Shell>
  );
}

/* -------------------------------------------------------------------------- */
/* Struttura della pagina                                                      */
/* -------------------------------------------------------------------------- */

function Shell({ lead, note, children }: { lead?: string; note?: string; children: ReactNode }) {
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="I tuoi match" lead={lead} />
      {note && <p className="mt-2 max-w-2xl text-sm text-ink-faint">{note}</p>}
      {children}
    </div>
  );
}

function FilterToggle({
  pressed,
  onClick,
  count,
  disabled,
  title,
  children,
}: {
  pressed: boolean;
  onClick: () => void;
  count: number;
  disabled?: boolean;
  title?: string;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      disabled={disabled}
      title={title}
      onClick={onClick}
      className={cn(
        "jm-press inline-flex h-11 items-center gap-2 rounded-full border px-4 text-sm font-medium sm:h-10",
        pressed
          ? "border-accent bg-accent text-paper-2"
          : "border-line-hard bg-paper-2 text-ink hover:border-accent",
        disabled && "border-dashed text-ink-soft hover:border-line-hard",
      )}
    >
      {children}
      <span className="font-mono text-xs opacity-80">{count}</span>
    </button>
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
      <span className="text-xs font-medium text-ink-soft">{label}</span>
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

function MatchCard({
  m,
  saved,
  showCategory,
  onOpen,
}: {
  m: FeedMatch;
  saved?: TrackedMatch;
  showCategory: boolean;
  onOpen: () => void;
}) {
  const skills = m.matched_skills.slice(0, CARD_SKILLS);
  const extra = m.matched_skills.length - skills.length;
  const place = regionLabel(m.region);

  return (
    <article className="group relative flex flex-col rounded-2xl border border-line bg-paper-2 p-4 transition-colors hover:border-line-hard">
      <div className="flex items-start gap-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-[17px] font-medium leading-snug tracking-[-0.01em] [overflow-wrap:anywhere]">
            {/* Un solo punto di arresto: il titolo. Il suo ::after copre tutta la card,
                quindi anche «Apri dettagli» (solo visivo) apre il dettaglio con un clic. */}
            <button
              type="button"
              onClick={onOpen}
              className="jm-stretch text-left after:absolute after:inset-0 after:rounded-2xl after:content-[''] focus-visible:outline-none focus-visible:after:ring-2 focus-visible:after:ring-accent"
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
        <CardScore
          m={{
            coverage: m.coverage,
            skillsMeasured: m.skills_measured,
            have: m.matched_skills,
            belowThreshold: m.below_threshold,
          }}
        />
      </div>

      <div className="flex items-center justify-between gap-3 pt-3">
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-soft">
          {saved && isTracked(saved.status) && <StatusTag status={saved.status} />}
          {m.is_new && !saved && (
            <span className="rounded-full border border-line-hard px-2 py-0.5 font-medium">Nuovo da ieri</span>
          )}
          {showCategory && <span>{CATEGORY_LABEL[m.category] ?? m.category}</span>}
        </span>
        <span
          aria-hidden
          className="inline-flex h-10 shrink-0 items-center gap-1 rounded-full border border-line-hard bg-paper-2 pl-4 pr-3 text-sm font-medium text-ink transition-colors group-hover:border-accent"
        >
          Apri dettagli
          <ChevronRight className="h-4 w-4" />
        </span>
      </div>
    </article>
  );
}
