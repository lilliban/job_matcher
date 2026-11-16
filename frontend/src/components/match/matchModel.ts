/**
 * Un annuncio visto da una sola parte: lo stesso modello per il feed ("I tuoi
 * match"), per le ricerche già fatte e per Candidature. Il pannello di dettaglio
 * e le etichette leggono solo questo, così l'annuncio ha ovunque la stessa
 * percentuale, le stesse skill "Hai" e "Ti mancano" e le stesse azioni.
 */
import type { FeedMatch, SavedMatch, TrackedMatch } from "@/api/queries";

/** Soglia di copertura del feed: COVERAGE_THRESHOLD in app/services/coverage.py */
export const THRESHOLD_PCT = 60;
export const BELOW_LABEL = `Sotto il ${THRESHOLD_PCT}%`;
/** Sotto questa soglia di skill misurate la percentuale dice poco (vedi pipeline.py). */
export const LOW_DATA_SKILLS = 3;

export const CATEGORY_LABEL: Record<string, string> = {
  analytics_ai: "Dati e AI",
  consulting_security: "Consulenza e sicurezza",
  software: "Sviluppo software",
  support_qa: "Supporto e QA",
  unclassified: "Altri ruoli",
};

/** Nome dello stato di una candidatura, al singolare: per menu e etichette. */
export const STATUS_LABEL: Record<string, string> = {
  new: "Nuovo",
  saved: "Salvata",
  applied: "Inviata",
  waiting: "In attesa",
  interview: "Colloquio",
  rejected: "Rifiutata",
  accepted: "Accettata",
  discarded: "Scartato",
};

/** Gli stati di una candidatura, nell'ordine del menu e della pagina Candidature. */
export const TRACKED_STATUSES = ["saved", "applied", "waiting", "interview", "rejected", "accepted"] as const;
export type TrackedStatus = (typeof TRACKED_STATUSES)[number];

/** Valore del menu che toglie l'annuncio dalle candidature (stato "new" nel database). */
export const REMOVE_VALUE = "__remove__";

export function isTracked(status: string | null | undefined): status is TrackedStatus {
  return !!status && (TRACKED_STATUSES as readonly string[]).includes(status);
}

// Valori di FeedMatch.region che non sono un codice paese
export const REGION_REMOTE_EU = "remote_eu";
export const REGION_UNKNOWN = "unknown";
export const NO_COUNTRY_LABEL = "Paese non indicato";

const regionNames =
  typeof Intl !== "undefined" && "DisplayNames" in Intl
    ? new Intl.DisplayNames(["it"], { type: "region" })
    : null;

export function countryName(code: string): string {
  try {
    return regionNames?.of(code.toUpperCase()) ?? code;
  } catch {
    return code;
  }
}

/** Etichetta del luogo: paese, "Remoto in Europa" o "Paese non indicato". */
export function regionLabel(region: string | null | undefined): string {
  if (!region || region === REGION_UNKNOWN) return NO_COUNTRY_LABEL;
  if (region === REGION_REMOTE_EU) return "Remoto in Europa";
  return countryName(region);
}

export function dateLabel(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("it-IT", { day: "numeric", month: "short", year: "numeric" });
}

export interface MatchView {
  /** Chiave stabile per le liste */
  key: string;
  title: string;
  company: string | null;
  /** Codice paese, "remote_eu" o "unknown" */
  region: string;
  kind: "job" | "thesis";
  sourceUrl: string | null;
  /** 0–1; null se nel testo non c'è nessuna skill riconoscibile */
  coverage: number | null;
  skillsMeasured: number;
  have: string[];
  missingRequired: string[];
  missingNice: string[];
  belowThreshold: boolean;
  description: string | null;
  /** Feed: primo avvistamento. Salvato dal feed: quando l'hai salvato. Ricerca: quando l'ha trovato. */
  date: string | null;
  dateKind: "seen" | "saved" | "found";
  /** Gruppo di ruoli (solo feed) */
  category: string | null;
  origin: "feed" | "search";
  /** Presente se l'annuncio è già nel database (salvato o trovato da una ricerca) */
  matchId: string | null;
  status: string | null;
  /** Punteggio della ricerca: la "Pertinenza". Solo per i match delle ricerche. */
  pertinenza: number | null;
  pertinenzaUniform: boolean;
  /** Il feed originale, per poterlo salvare */
  feed: FeedMatch | null;
}

export function coveragePct(v: { coverage: number | null }): number | null {
  return v.coverage == null ? null : Math.round(v.coverage * 100);
}

export function isLowData(v: Pick<MatchView, "coverage" | "skillsMeasured">): boolean {
  return v.coverage != null && v.skillsMeasured < LOW_DATA_SKILLS;
}

/** "2 di 3 skill": su quante skill dell'annuncio è calcolata la percentuale. */
export function skillsBasis(v: Pick<MatchView, "have" | "skillsMeasured">): string {
  return `${v.have.length} di ${v.skillsMeasured} skill`;
}

/** Il feed, eventualmente con la candidatura già salvata per lo stesso indirizzo. */
export function fromFeed(m: FeedMatch, saved?: TrackedMatch | null): MatchView {
  return {
    key: `feed|${m.source_url ?? ""}|${m.title ?? ""}|${m.company_name ?? ""}`,
    title: m.title ?? "Annuncio senza titolo",
    company: m.company_name,
    region: m.region,
    kind: m.kind,
    sourceUrl: m.source_url,
    coverage: m.coverage,
    skillsMeasured: m.skills_measured,
    have: m.matched_skills,
    missingRequired: m.missing_required,
    missingNice: m.missing_nice,
    belowThreshold: m.below_threshold,
    description: m.description,
    date: m.first_seen_at,
    dateKind: "seen",
    category: m.category,
    origin: "feed",
    matchId: saved?.id ?? null,
    status: saved?.status ?? null,
    pertinenza: null,
    pertinenzaUniform: false,
    feed: m,
  };
}

/** Un match già nel database: di una ricerca o salvato dal feed. */
export function fromMatch(m: SavedMatch | TrackedMatch): MatchView {
  const l = m.listing;
  const country = m.country_code?.toUpperCase() ?? REGION_UNKNOWN;
  return {
    key: `match|${m.id}`,
    title: l?.title ?? "Annuncio senza titolo",
    company: l?.company_name ?? null,
    region: country,
    kind: "job",
    sourceUrl: l?.source_url ?? null,
    coverage: m.coverage,
    skillsMeasured: m.skills_measured,
    have: m.have,
    missingRequired: m.missing_required,
    missingNice: m.missing_nice,
    belowThreshold: m.below_threshold,
    description: l?.requirements_raw || l?.description || null,
    date: m.created_at,
    dateKind: m.origin === "feed" ? "saved" : "found",
    category: null,
    origin: m.origin,
    matchId: m.id,
    status: m.status,
    pertinenza: m.origin === "search" ? m.score : null,
    pertinenzaUniform: m.pertinenza_uniform,
    feed: null,
  };
}
