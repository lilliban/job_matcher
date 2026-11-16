/**
 * Hook TanStack Query centralizzati per l'API JobMatcher.
 *
 * Ogni view importa da qui i suoi hook di lettura/scrittura, evitando di
 * duplicare la logica `useQuery`/`useMutation` sparsa nei componenti.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from "@tanstack/react-query";

import { api } from "./client";
import type {
  BaseDocumentIn,
  BaseDocumentOut,
  CollectionCreate,
  CollectionMemberCreate,
  CollectionMemberOut,
  CollectionOut,
  CompanySearchRequest,
  CompanySuggestion,
  EducationCreate,
  EducationOut,
  ExperienceCreate,
  ExperienceOut,
  GeneratedDocumentOut,
  IntelligenceReportOut,
  JobListingOut,
  MatchDetailOut,
  MatchOut,
  MatchStatusUpdate,
  PreferredCompanyCreate,
  PreferredCompanyOut,
  SearchLogOut,
  SearchSessionCreate,
  SearchMode,
  SearchSessionOut,
  SearchSessionUpdate,
  SessionHardSkillCreate,
  SessionHardSkillOut,
  SessionStatusOut,
  SimilarCompaniesRequest,
  SkillSuggestion,
  SoftSkillCreate,
  SoftSkillOut,
  TargetCompanyCreate,
  TargetCompanyOut,
  UserCreate,
  UserHardSkillCreate,
  UserHardSkillOut,
  UserHardSkillUpdate,
  UserLanguageCreate,
  UserLanguageOut,
  UserOut,
  UserUpdate,
} from "./schemas";

/* -------------------------------------------------------------------------- */
/* Users                                                                       */
/* -------------------------------------------------------------------------- */

export const userKeys = {
  all: ["users"] as const,
  detail: (id: string) => ["users", id] as const,
  softSkills: (id: string) => ["users", id, "soft-skills"] as const,
  hardSkills: (id: string) => ["users", id, "hard-skills"] as const,
  languages: (id: string) => ["users", id, "languages"] as const,
  experiences: (id: string) => ["users", id, "experiences"] as const,
  education: (id: string) => ["users", id, "education"] as const,
  preferredCompanies: (id: string) => ["users", id, "preferred-companies"] as const,
  baseDocuments: (id: string) => ["users", id, "base-documents"] as const,
  sessions: (id: string) => ["users", id, "sessions"] as const,
  collections: (id: string) => ["users", id, "collections"] as const,
};

export function useUsers() {
  return useQuery({
    queryKey: userKeys.all,
    queryFn: () => api<UserOut[]>("/api/users"),
  });
}

export function useUser(userId: string | null) {
  return useQuery({
    queryKey: userKeys.detail(userId ?? ""),
    queryFn: () => api<UserOut>(`/api/users/${userId}`),
    enabled: !!userId,
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UserCreate) => api<UserOut>("/api/users", { method: "POST", json: body }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: userKeys.all });
      qc.setQueryData(userKeys.detail(created.id), created);
    },
  });
}

export function useUpdateUser(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UserUpdate) =>
      api<UserOut>(`/api/users/${userId}`, { method: "PATCH", json: body }),
    onSuccess: (updated) => {
      qc.setQueryData(userKeys.detail(userId), updated);
      qc.invalidateQueries({ queryKey: userKeys.all });
    },
  });
}

/* -------- User → soft skills -------- */

export function useSoftSkills(userId: string | null) {
  return useQuery({
    queryKey: userKeys.softSkills(userId ?? ""),
    queryFn: () => api<SoftSkillOut[]>(`/api/users/${userId}/soft-skills`),
    enabled: !!userId,
  });
}

export function useAddSoftSkill(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SoftSkillCreate) =>
      api<SoftSkillOut>(`/api/users/${userId}/soft-skills`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.softSkills(userId) }),
  });
}

export function useDeleteSoftSkill(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (skillId: string) =>
      api(`/api/users/${userId}/soft-skills/${skillId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.softSkills(userId) }),
  });
}

/* -------- User → hard skills -------- */

export function useHardSkills(userId: string | null) {
  return useQuery({
    queryKey: userKeys.hardSkills(userId ?? ""),
    queryFn: () => api<UserHardSkillOut[]>(`/api/users/${userId}/hard-skills`),
    enabled: !!userId,
  });
}

export function useAddHardSkill(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UserHardSkillCreate) =>
      api<UserHardSkillOut>(`/api/users/${userId}/hard-skills`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.hardSkills(userId) }),
  });
}

export function useUpdateHardSkill(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ skillId, body }: { skillId: string; body: UserHardSkillUpdate }) =>
      api<UserHardSkillOut>(`/api/users/${userId}/hard-skills/${skillId}`, {
        method: "PATCH",
        json: body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.hardSkills(userId) }),
  });
}

export function useDeleteHardSkill(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (skillId: string) =>
      api(`/api/users/${userId}/hard-skills/${skillId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.hardSkills(userId) }),
  });
}

/* -------- User → languages -------- */

export function useLanguages(userId: string | null) {
  return useQuery({
    queryKey: userKeys.languages(userId ?? ""),
    queryFn: () => api<UserLanguageOut[]>(`/api/users/${userId}/languages`),
    enabled: !!userId,
  });
}

export function useAddLanguage(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UserLanguageCreate) =>
      api<UserLanguageOut>(`/api/users/${userId}/languages`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.languages(userId) }),
  });
}

export function useDeleteLanguage(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (langId: string) =>
      api(`/api/users/${userId}/languages/${langId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.languages(userId) }),
  });
}

/* -------- User → experiences -------- */

export function useExperiences(userId: string | null) {
  return useQuery({
    queryKey: userKeys.experiences(userId ?? ""),
    queryFn: () => api<ExperienceOut[]>(`/api/users/${userId}/experiences`),
    enabled: !!userId,
  });
}

export function useAddExperience(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ExperienceCreate) =>
      api<ExperienceOut>(`/api/users/${userId}/experiences`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.experiences(userId) }),
  });
}

export function useDeleteExperience(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (expId: string) =>
      api(`/api/users/${userId}/experiences/${expId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.experiences(userId) }),
  });
}

/* -------- User → education -------- */

export function useEducation(userId: string | null) {
  return useQuery({
    queryKey: userKeys.education(userId ?? ""),
    queryFn: () => api<EducationOut[]>(`/api/users/${userId}/education`),
    enabled: !!userId,
  });
}

export function useAddEducation(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: EducationCreate) =>
      api<EducationOut>(`/api/users/${userId}/education`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.education(userId) }),
  });
}

export function useDeleteEducation(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (eduId: string) =>
      api(`/api/users/${userId}/education/${eduId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.education(userId) }),
  });
}

/* -------- User → preferred companies -------- */

export function usePreferredCompanies(userId: string | null) {
  return useQuery({
    queryKey: userKeys.preferredCompanies(userId ?? ""),
    queryFn: () => api<PreferredCompanyOut[]>(`/api/users/${userId}/preferred-companies`),
    enabled: !!userId,
  });
}

export function useAddPreferredCompany(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: PreferredCompanyCreate) =>
      api<PreferredCompanyOut>(`/api/users/${userId}/preferred-companies`, {
        method: "POST",
        json: body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.preferredCompanies(userId) }),
  });
}

export function useDeletePreferredCompany(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (companyId: string) =>
      api(`/api/users/${userId}/preferred-companies/${companyId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.preferredCompanies(userId) }),
  });
}

/* -------------------------------------------------------------------------- */
/* Skills catalog + suggerimenti                                              */
/* -------------------------------------------------------------------------- */

export function useSoftSkillsCatalog() {
  return useQuery({
    queryKey: ["skills", "soft", "catalog"],
    queryFn: () => api<SkillSuggestion[]>("/api/skills/soft"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSuggestSoftSkills() {
  return useMutation({
    mutationFn: ({ skillName, limit = 5 }: { skillName: string; limit?: number }) =>
      api<SkillSuggestion[]>(
        `/api/skills/soft/${encodeURIComponent(skillName)}/similar`,
        { query: { limit } },
      ),
  });
}

export function useSuggestSkillsForRole() {
  return useMutation({
    mutationFn: ({ role, limit = 12 }: { role: string; limit?: number }) =>
      api<SkillSuggestion[]>("/api/skills/suggest", { query: { role, limit } }),
  });
}

/* -------------------------------------------------------------------------- */
/* Sessions                                                                    */
/* -------------------------------------------------------------------------- */

export const sessionKeys = {
  list: (userId: string) => ["users", userId, "sessions"] as const,
  detail: (userId: string, sessionId: string) =>
    ["users", userId, "sessions", sessionId] as const,
  status: (userId: string, sessionId: string) =>
    ["users", userId, "sessions", sessionId, "status"] as const,
  logs: (userId: string, sessionId: string) =>
    ["users", userId, "sessions", sessionId, "logs"] as const,
  listings: (userId: string, sessionId: string) =>
    ["users", userId, "sessions", sessionId, "listings"] as const,
  matches: (userId: string, sessionId: string) =>
    ["users", userId, "sessions", sessionId, "matches"] as const,
  skills: (userId: string, sessionId: string) =>
    ["users", userId, "sessions", sessionId, "hard-skills"] as const,
  companies: (userId: string, sessionId: string) =>
    ["users", userId, "sessions", sessionId, "companies"] as const,
  intelligence: (userId: string, sessionId: string) =>
    ["users", userId, "sessions", sessionId, "intelligence"] as const,
};

export function useSessions(userId: string | null) {
  return useQuery({
    queryKey: userKeys.sessions(userId ?? ""),
    queryFn: () => api<SearchSessionOut[]>(`/api/users/${userId}/sessions`),
    enabled: !!userId,
  });
}

export function useSession(userId: string | null, sessionId: string | null) {
  return useQuery({
    queryKey: sessionKeys.detail(userId ?? "", sessionId ?? ""),
    queryFn: () => api<SearchSessionOut>(`/api/users/${userId}/sessions/${sessionId}`),
    enabled: !!userId && !!sessionId,
  });
}

export function useCreateSession(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SearchSessionCreate) =>
      api<SearchSessionOut>(`/api/users/${userId}/sessions`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.sessions(userId) }),
  });
}

export function useUpdateSession(userId: string, sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SearchSessionUpdate) =>
      api<SearchSessionOut>(`/api/users/${userId}/sessions/${sessionId}`, {
        method: "PATCH",
        json: body,
      }),
    onSuccess: (updated) => {
      qc.setQueryData(sessionKeys.detail(userId, sessionId), updated);
      qc.invalidateQueries({ queryKey: userKeys.sessions(userId) });
    },
  });
}

export function useDeleteSession(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      api(`/api/users/${userId}/sessions/${sessionId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.sessions(userId) }),
  });
}

export function useStartSession(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      api(`/api/users/${userId}/sessions/${sessionId}/run`, { method: "POST" }),
    onSuccess: (_, sessionId) => {
      qc.invalidateQueries({ queryKey: sessionKeys.status(userId, sessionId) });
    },
  });
}

export function useCancelSession(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      api(`/api/users/${userId}/sessions/${sessionId}/cancel`, { method: "POST" }),
    onSuccess: (_, sessionId) => {
      qc.invalidateQueries({ queryKey: sessionKeys.status(userId, sessionId) });
    },
  });
}

/**
 * Stato della ricerca — polling ogni 2.5s finché non è terminale.
 * Usa refetchInterval condizionale (esattamente come startPolling/stopPolling
 * del vanilla).
 */
export function useSessionStatus(userId: string | null, sessionId: string | null) {
  return useQuery({
    queryKey: sessionKeys.status(userId ?? "", sessionId ?? ""),
    queryFn: () => api<SessionStatusOut>(`/api/users/${userId}/sessions/${sessionId}/status`),
    enabled: !!userId && !!sessionId,
    refetchInterval: (query) => {
      const s = query.state.data;
      if (!s) return 2500;
      if (["completed", "error", "cancelled"].includes(s.status)) return false;
      return 2500;
    },
  });
}

export function useSessionLogs(
  userId: string | null,
  sessionId: string | null,
  polling = true,
) {
  return useQuery({
    queryKey: sessionKeys.logs(userId ?? "", sessionId ?? ""),
    queryFn: () =>
      api<SearchLogOut[]>(`/api/users/${userId}/sessions/${sessionId}/logs`, {
        query: { limit: 500 },
      }),
    enabled: !!userId && !!sessionId,
    refetchInterval: polling ? 2500 : false,
  });
}

export function useSessionListings(userId: string | null, sessionId: string | null) {
  return useQuery({
    queryKey: sessionKeys.listings(userId ?? "", sessionId ?? ""),
    queryFn: () =>
      api<JobListingOut[]>(`/api/users/${userId}/sessions/${sessionId}/listings`),
    enabled: !!userId && !!sessionId,
  });
}

export function useSessionMatches(userId: string | null, sessionId: string | null) {
  return useQuery({
    queryKey: sessionKeys.matches(userId ?? "", sessionId ?? ""),
    queryFn: () =>
      api<SavedMatch[]>(`/api/users/${userId}/sessions/${sessionId}/matches`),
    enabled: !!userId && !!sessionId,
  });
}

export function useSessionSkills(userId: string | null, sessionId: string | null) {
  return useQuery({
    queryKey: sessionKeys.skills(userId ?? "", sessionId ?? ""),
    queryFn: () =>
      api<SessionHardSkillOut[]>(`/api/users/${userId}/sessions/${sessionId}/hard-skills`),
    enabled: !!userId && !!sessionId,
  });
}

export function useAddSessionSkill(userId: string, sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: SessionHardSkillCreate) =>
      api<SessionHardSkillOut>(`/api/users/${userId}/sessions/${sessionId}/hard-skills`, {
        method: "POST",
        json: body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: sessionKeys.skills(userId, sessionId) }),
  });
}

export function useDeleteSessionSkill(userId: string, sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (skillId: string) =>
      api(`/api/users/${userId}/sessions/${sessionId}/hard-skills/${skillId}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: sessionKeys.skills(userId, sessionId) }),
  });
}

export function useSessionCompanies(userId: string | null, sessionId: string | null) {
  return useQuery({
    queryKey: sessionKeys.companies(userId ?? "", sessionId ?? ""),
    queryFn: () =>
      api<TargetCompanyOut[]>(`/api/users/${userId}/sessions/${sessionId}/companies`),
    enabled: !!userId && !!sessionId,
  });
}

export function useAddSessionCompany(userId: string, sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TargetCompanyCreate) =>
      api<TargetCompanyOut>(`/api/users/${userId}/sessions/${sessionId}/companies`, {
        method: "POST",
        json: body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: sessionKeys.companies(userId, sessionId) }),
  });
}

export function useDeleteSessionCompany(userId: string, sessionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (companyId: string) =>
      api(`/api/users/${userId}/sessions/${sessionId}/companies/${companyId}`, {
        method: "DELETE",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: sessionKeys.companies(userId, sessionId) }),
  });
}

export function useIntelligenceReport(userId: string | null, sessionId: string | null) {
  return useQuery({
    queryKey: sessionKeys.intelligence(userId ?? "", sessionId ?? ""),
    queryFn: () =>
      api<IntelligenceReportOut>(`/api/users/${userId}/sessions/${sessionId}/intelligence`),
    enabled: !!userId && !!sessionId,
  });
}

/* -------------------------------------------------------------------------- */
/* Companies (livello utente)                                                  */
/* -------------------------------------------------------------------------- */

export function useSearchCompanies() {
  const search = (userId: string, body: CompanySearchRequest) =>
    api<CompanySuggestion[]>(`/api/users/${userId}/companies/search`, {
      method: "POST",
      json: body,
    });
  return search;
}

export function useSuggestSimilarCompanies() {
  return useMutation({
    mutationFn: ({ userId, body }: { userId: string; body: SimilarCompaniesRequest }) =>
      api<CompanySuggestion[]>(`/api/users/${userId}/companies/similar`, {
        method: "POST",
        json: body,
      }),
  });
}

/* -------------------------------------------------------------------------- */
/* Matches & Documents                                                         */
/* -------------------------------------------------------------------------- */

export function useMatch(matchId: string | null) {
  return useQuery({
    queryKey: ["matches", matchId],
    queryFn: () => api<MatchDetailOut>(`/api/matches/${matchId}`),
    enabled: !!matchId,
  });
}

export function useUpdateMatchStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ matchId, body }: { matchId: string; body: MatchStatusUpdate }) =>
      api<MatchOut>(`/api/matches/${matchId}/status`, { method: "PATCH", json: body }),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["matches", vars.matchId] });
      // lo stato compare in Candidature e nell'elenco di ogni ricerca
      qc.invalidateQueries({ queryKey: ["users"], predicate: (q) => isMatchListKey(q.queryKey) });
    },
  });
}

/** Le liste che mostrano uno stato: candidature e match di una ricerca. */
function isMatchListKey(key: readonly unknown[]): boolean {
  return key[2] === "tracked" || (key[2] === "sessions" && key[4] === "matches");
}

export function useMatchDocuments(matchId: string | null) {
  return useQuery({
    queryKey: ["matches", matchId, "documents"],
    queryFn: () => api<GeneratedDocumentOut[]>(`/api/matches/${matchId}/documents`),
    enabled: !!matchId,
  });
}

/* -------------------------------------------------------------------------- */
/* Match dal feed (copertura skill, senza LLM)                                 */
/* -------------------------------------------------------------------------- */

export interface FeedMatch {
  title: string | null;
  company_name: string | null;
  country_code: string | null;
  /** "CH" | "DE" | "NL", "remote_eu" (remoto aperto all'Europa) o "unknown" */
  region: string;
  /** "thesis" per tesi e dottorati: fuori dalla lista principale */
  kind: "job" | "thesis";
  source_url: string | null;
  /** 1 = più in linea con il profilo, 5 = ruolo non classificato */
  priority: number;
  category: string;
  /** 0–1; null se nel testo dell'annuncio non c'è nessuna skill riconoscibile */
  coverage: number | null;
  below_threshold: boolean;
  matched_skills: string[];
  missing_required: string[];
  missing_nice: string[];
  /** Skill dell'annuncio su cui è calcolata la copertura (richieste + gradite); sotto 3 la percentuale è poco affidabile */
  skills_measured: number;
  first_seen_at: string | null;
  /** Il testo su cui è calcolata la copertura */
  description: string | null;
  /** Visto per la prima volta da ieri, e sopra la soglia (o non misurabile ma di priorità 1) */
  is_new: boolean;
}

export const feedKey = (userId: string | null) => ["users", userId, "feed-matches"] as const;

function feedQueryOptions(userId: string | null) {
  return {
    queryKey: feedKey(userId),
    queryFn: () => api<FeedMatch[]>("/api/matches/feed", { query: { user_id: userId } }),
    enabled: !!userId,
    // il feed cambia poche volte al giorno e il confronto è pesante
    staleTime: 5 * 60 * 1000,
    // un 503 "feed non disponibile" non si risolve riprovando subito
    retry: false,
  };
}

export function useFeedMatches(userId: string | null) {
  return useQuery(feedQueryOptions(userId));
}

/** Quanti annunci "Nuovi da ieri" ci sono (tesi escluse). undefined finché il feed non è arrivato. */
export function useNewMatchCount(userId: string | null): number | undefined {
  const { data } = useQuery({
    ...feedQueryOptions(userId),
    select: (list: FeedMatch[]) => list.filter((m) => m.is_new && m.kind !== "thesis").length,
  });
  return data;
}

/* -------------------------------------------------------------------------- */
/* Candidature: annunci salvati dal feed o trovati da una ricerca               */
/* -------------------------------------------------------------------------- */

/** La stessa metrica del feed, calcolata dal server su un annuncio salvato. */
export interface MatchInsight {
  coverage: number | null;
  skills_measured: number;
  have: string[];
  missing_required: string[];
  missing_nice: string[];
  below_threshold: boolean;
  country_code: string | null;
  /** Titolo non tech o copertura zero: in "Ricerche fatte" va in fondo */
  off_profile: boolean;
  origin: "search" | "feed";
  /** Il punteggio della ricerca ("Pertinenza") è uguale per tutti gli annunci */
  pertinenza_uniform: boolean;
}

/** Un match di una ricerca, con la copertura. `score` è la "Pertinenza". */
export type SavedMatch = Omit<MatchDetailOut, keyof MatchInsight> & MatchInsight;

export interface DocumentBrief {
  id: string;
  doc_type: string;
  created_at: string;
}

export type TrackedMatch = Omit<SavedMatch, "documents"> & { documents: DocumentBrief[] };

export interface TrackedGroup {
  status: string;
  label: string;
  count: number;
  items: TrackedMatch[];
}

export const trackedKey = (userId: string | null) => ["users", userId, "tracked"] as const;

export function useTrackedMatches(userId: string | null) {
  return useQuery({
    queryKey: trackedKey(userId),
    queryFn: () => api<TrackedGroup[]>("/api/matches/tracked", { query: { user_id: userId } }),
    enabled: !!userId,
  });
}

/** Salva un annuncio del feed (idempotente). Senza `status` diventa "Salvata". */
export function useSaveFeedMatch(userId: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ad, status }: { ad: FeedMatch; status?: string }) =>
      api<TrackedMatch>("/api/matches/from-feed", {
        method: "POST",
        json: {
          user_id: userId,
          title: ad.title ?? "Annuncio senza titolo",
          company_name: ad.company_name,
          source_url: ad.source_url,
          country_code: ad.country_code,
          region: ad.region,
          description: ad.description,
          first_seen_at: ad.first_seen_at,
          status: status ?? null,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: trackedKey(userId) });
    },
  });
}

/* -------------------------------------------------------------------------- */
/* Base documents                                                              */
/* -------------------------------------------------------------------------- */

export function useBaseDocuments(userId: string | null) {
  return useQuery({
    queryKey: userKeys.baseDocuments(userId ?? ""),
    queryFn: () => api<BaseDocumentOut[]>(`/api/users/${userId}/base-documents`),
    enabled: !!userId,
  });
}

export function useUpsertBaseDocument(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ docType, body }: { docType: string; body: BaseDocumentIn }) =>
      api<BaseDocumentOut>(`/api/users/${userId}/base-documents/${docType}`, {
        method: "PUT",
        json: body,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.baseDocuments(userId) }),
  });
}

/* -------------------------------------------------------------------------- */
/* Collections                                                                 */
/* -------------------------------------------------------------------------- */

export function useCollections(userId: string | null) {
  return useQuery({
    queryKey: userKeys.collections(userId ?? ""),
    queryFn: () => api<CollectionOut[]>(`/api/users/${userId}/collections`),
    enabled: !!userId,
  });
}

export function useCreateCollection(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CollectionCreate) =>
      api<CollectionOut>(`/api/users/${userId}/collections`, { method: "POST", json: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.collections(userId) }),
  });
}

export function useDeleteCollection(userId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (collectionId: string) =>
      api(`/api/users/${userId}/collections/${collectionId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: userKeys.collections(userId) }),
  });
}

export function useCollectionMembers(userId: string | null, collectionId: string | null) {
  return useQuery({
    queryKey: ["users", userId, "collections", collectionId, "members"],
    queryFn: () =>
      api<CollectionMemberOut[]>(
        `/api/users/${userId}/collections/${collectionId}/members`,
      ),
    enabled: !!userId && !!collectionId,
  });
}

export function useAddCollectionMember(userId: string, collectionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CollectionMemberCreate) =>
      api<CollectionMemberOut>(
        `/api/users/${userId}/collections/${collectionId}/members`,
        { method: "POST", json: body },
      ),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["users", userId, "collections", collectionId, "members"],
      }),
  });
}

export function useDeleteCollectionMember(userId: string, collectionId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) =>
      api(`/api/users/${userId}/collections/${collectionId}/members/${memberId}`, {
        method: "DELETE",
      }),
    onSuccess: () =>
      qc.invalidateQueries({
        queryKey: ["users", userId, "collections", collectionId, "members"],
      }),
  });
}

/* -------------------------------------------------------------------------- */
/* Geo                                                                         */
/* -------------------------------------------------------------------------- */

export function useGeoTree() {
  return useQuery({
    queryKey: ["geo"],
    queryFn: () => api<Record<string, unknown>>("/api/geo"),
    staleTime: 60 * 60 * 1000,
  });
}

/* -------------------------------------------------------------------------- */
/* Helper — mutation con toast (usage puramente ergonomico)                    */
/* -------------------------------------------------------------------------- */

export type ApiMutationOptions<TData, TVars> = Omit<
  UseMutationOptions<TData, Error, TVars>,
  "mutationFn"
>;

/* -------------------------------------------------------------------------- */
/* Candidatura da link                                                         */
/* -------------------------------------------------------------------------- */

export interface ApplicationListing {
  title: string;
  company_name: string;
  location: string | null;
  requirements_raw: string;
  source_url: string | null;
}

export interface ApplicationResult {
  listing: ApplicationListing;
  documents: Partial<Record<"cv" | "cover_letter", string>>;
  guidelines_chars: number;
  llm_model: string | null;
  /** La candidatura a cui sono stati agganciati i documenti, se ne è stata indicata una */
  match_id: string | null;
}

export function useGenerateApplication() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (formData: FormData) =>
      api<ApplicationResult>("/api/applications/generate", {
        method: "POST",
        formData,
      }),
    onSuccess: (data) => {
      // i documenti nuovi compaiono nella candidatura e nelle sue righe
      if (data.match_id) {
        qc.invalidateQueries({ queryKey: ["matches", data.match_id] });
        qc.invalidateQueries({ queryKey: ["users"], predicate: (q) => isMatchListKey(q.queryKey) });
      }
    },
  });
}

/* -------------------------------------------------------------------------- */
/* Creazione profilo (a mano / da CV)                                          */
/* -------------------------------------------------------------------------- */

export interface CvDraft {
  name: string;
  email: string;
  phone: string;
  location: string;
  bio: string;
  hard_skills: string[];
  soft_skills: string[];
  languages: Array<{ language: string; level: string }>;
  experiences: Array<{
    company: string;
    role: string;
    start_date: string;
    end_date: string;
    description: string;
  }>;
  education: Array<{ institution: string; degree: string; field: string; year: string }>;
}

export interface ParsedCv {
  profile: Partial<{
    name: string | null;
    email: string | null;
    phone: string | null;
    location: string | null;
    bio: string | null;
    hard_skills: string[];
    soft_skills: string[];
    languages: Array<{ language?: string | null; level?: string | null }>;
    experiences: Array<Record<string, string | null>>;
    education: Array<Record<string, string | null>>;
  }>;
  critique: string | null;
  cv_text: string;
}

export function useParseCv() {
  return useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api<ParsedCv>("/api/onboarding/parse-cv", { method: "POST", formData: fd });
    },
  });
}

export function useCreateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<CvDraft> & { name: string; email: string; cv_text?: string | null }) =>
      api<UserOut>("/api/onboarding/create", { method: "POST", json: body }),
    onSuccess: (created) => {
      qc.invalidateQueries({ queryKey: userKeys.all });
      qc.setQueryData(userKeys.detail(created.id), created);
    },
  });
}

/* -------------------------------------------------------------------------- */
/* Suggerimenti (advisor)                                                      */
/* -------------------------------------------------------------------------- */

export interface RoleSuggestion {
  role: string;
  reason: string;
  new_postings: number;
}

export interface RolesAdvice {
  roles: RoleSuggestion[];
  news: {
    total: number;
    matching_roles: number;
    per_role: Array<{ role: string; count: number }>;
    sample: Array<{ title: string; company_name: string; location: string | null }>;
  };
}

export interface SkillAdvice {
  name: string;
  why?: string;
}

export function useRoleAdvice(userId: string | null, since: string | null) {
  return useQuery({
    queryKey: ["users", userId, "advisor", "roles", since],
    queryFn: () =>
      api<RolesAdvice>(`/api/users/${userId}/advisor/roles`, { query: { since } }),
    enabled: !!userId,
    staleTime: 10 * 60 * 1000,
  });
}

export function useSkillAdvice(userId: string | null, signature: string) {
  return useQuery({
    queryKey: ["users", userId, "advisor", "skills", signature],
    queryFn: () => api<{ skills: SkillAdvice[] }>(`/api/users/${userId}/advisor/skills`),
    enabled: !!userId,
    staleTime: 30 * 60 * 1000,
  });
}

export function useSimilarHardSkills(userId: string) {
  return useMutation({
    mutationFn: (name: string) =>
      api<{ skills: SkillAdvice[] }>(`/api/users/${userId}/advisor/skills/similar`, {
        query: { name },
      }),
  });
}

export interface RoleGap {
  role: string;
  coverage: number | null;
  missing: string[];
  show: boolean;
}

export function useRoleGap(userId: string | null, role: string) {
  return useQuery({
    queryKey: ["users", userId, "advisor", "gap", role],
    queryFn: () => api<RoleGap>(`/api/users/${userId}/advisor/role-gap`, { query: { role } }),
    enabled: !!userId && role.trim().length >= 3,
    staleTime: 30 * 60 * 1000,
  });
}

/* -------------------------------------------------------------------------- */
/* Catalogo aziende                                                            */
/* -------------------------------------------------------------------------- */

export interface CompanyCatalog {
  scopes: Array<{ key: string; label: string; hint: string; needs_country: boolean }>;
  sectors: Array<{ key: string; label: string }>;
  countries: Array<{ code: string; name: string }>;
}

export function useCompanyCatalog() {
  return useQuery({
    queryKey: ["company-catalog"],
    queryFn: () => api<CompanyCatalog>("/api/company-catalog"),
    staleTime: Infinity,
  });
}

export function useBrowseCompanies(userId: string) {
  return useMutation({
    mutationFn: (body: {
      scope: string;
      sector: string;
      country_code?: string | null;
      exclude?: string[];
      limit?: number;
    }) =>
      api<CompanySuggestion[]>(`/api/users/${userId}/companies/browse`, {
        method: "POST",
        json: body,
      }),
  });
}

export function useSimilarCompanies(userId: string) {
  return useMutation({
    mutationFn: (body: { selected_companies: string[]; limit?: number }) =>
      api<CompanySuggestion[]>(`/api/users/${userId}/companies/similar`, {
        method: "POST",
        json: { limit: 6, ...body },
      }),
  });
}

export function useSearchCompaniesByName(userId: string) {
  return useMutation({
    mutationFn: (query: string) =>
      api<CompanySuggestion[]>(`/api/users/${userId}/companies/search`, {
        method: "POST",
        json: { query, limit: 6 },
      }),
  });
}

/* -------------------------------------------------------------------------- */
/* Panoramica ricerche                                                         */
/* -------------------------------------------------------------------------- */

export interface SessionOverview {
  id: string;
  role_title: string;
  search_mode: SearchMode | string;
  preferred_country: string | null;
  location_pref: string | null;
  status: string;
  match_threshold: number;
  created_at: string;
  last_run_at: string | null;
  listings_count: number;
  matches_count: number;
  best_score: number | null;
  new_matches: number;
  companies_count: number;
}

export function useSessionsOverview(userId: string | null) {
  return useQuery({
    queryKey: ["users", userId, "sessions", "overview"],
    queryFn: () => api<SessionOverview[]>(`/api/users/${userId}/sessions/overview`),
    enabled: !!userId,
    // finché c'è una ricerca in corso i numeri cambiano
    refetchInterval: (q) => (q.state.data?.some((s) => s.status === "running") ? 3000 : false),
  });
}
