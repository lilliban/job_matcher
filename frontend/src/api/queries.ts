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
  CVParseResult,
  DocumentRegenerateRequest,
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

// Estrae profilo + critica da un CV PDF. Non scrive nulla sul profilo da
// sola: il chiamante mostra un'anteprima e sceglie cosa applicare tramite
// gli altri hook (useAddHardSkill, useAddExperience, ...).
export function useParseCv(userId: string) {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return api<CVParseResult>(`/api/users/${userId}/cv/parse`, {
        method: "POST",
        formData,
      });
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
      // "draft" = sessione creata ma non ancora avviata: nulla da pollare finché
      // l'utente non preme "Avvia ricerca" (altrimenti polling perpetuo appena
      // creata una sessione, prima ancora che parta qualcosa)
      if (["draft", "completed", "error", "cancelled"].includes(s.status)) return false;
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
      api<MatchDetailOut[]>(`/api/users/${userId}/sessions/${sessionId}/matches`),
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
    },
  });
}

export function useMatchDocuments(matchId: string | null) {
  return useQuery({
    queryKey: ["matches", matchId, "documents"],
    queryFn: () => api<GeneratedDocumentOut[]>(`/api/matches/${matchId}/documents`),
    enabled: !!matchId,
  });
}

// Genera (o rigenera) un documento su richiesta — non parte più da sola
// per ogni match, così non si spende quota LLM per documenti mai scaricati.
export function useRegenerateDocument(matchId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DocumentRegenerateRequest) =>
      api<GeneratedDocumentOut>(`/api/documents/regenerate/${matchId}`, {
        method: "POST",
        json: body,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["matches", matchId, "documents"] });
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
