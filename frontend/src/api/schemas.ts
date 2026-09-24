/**
 * Type helpers per estrarre gli schemi Pydantic da `types.ts` (auto-generato).
 * Usa questi alias invece di scrivere ovunque `components["schemas"]["Foo"]`.
 */

import type { components } from "./types";

type S = components["schemas"];

export type UserOut = S["UserOut"];
export type UserCreate = S["UserCreate"];
export type UserUpdate = S["UserUpdate"];

export type UserLanguageOut = S["UserLanguageOut"];
export type UserLanguageCreate = S["UserLanguageCreate"];

export type SoftSkillOut = S["SoftSkillOut"];
export type SoftSkillCreate = S["SoftSkillCreate"];

export type UserHardSkillOut = S["UserHardSkillOut"];
export type UserHardSkillCreate = S["UserHardSkillCreate"];
export type UserHardSkillUpdate = S["UserHardSkillUpdate"];

export type ExperienceOut = S["ExperienceOut"];
export type ExperienceCreate = S["ExperienceCreate"];

export type EducationOut = S["EducationOut"];
export type EducationCreate = S["EducationCreate"];

export type PreferredCompanyOut = S["PreferredCompanyOut"];
export type PreferredCompanyCreate = S["PreferredCompanyCreate"];

export type SearchSessionOut = S["SearchSessionOut"];
export type SearchSessionCreate = S["SearchSessionCreate"];
export type SearchSessionUpdate = S["SearchSessionUpdate"];
export type SessionStatusOut = S["SessionStatusOut"];
export type SearchLogOut = S["SearchLogOut"];

export type SessionHardSkillOut = S["SessionHardSkillOut"];
export type SessionHardSkillCreate = S["SessionHardSkillCreate"];

export type JobListingOut = S["JobListingOut"];
export type MatchOut = S["MatchOut"];
export type MatchDetailOut = S["MatchDetailOut"];
export type MatchStatusUpdate = S["MatchStatusUpdate"];

export type GeneratedDocumentOut = S["GeneratedDocumentOut"];
export type DocumentRegenerateRequest = S["DocumentRegenerateRequest"];

export type BaseDocumentOut = S["BaseDocumentOut"];
export type BaseDocumentIn = S["BaseDocumentIn"];

export type CollectionOut = S["CollectionOut"];
export type CollectionCreate = S["CollectionCreate"];
export type CollectionMemberOut = S["CollectionMemberOut"];
export type CollectionMemberCreate = S["CollectionMemberCreate"];

export type CompanySuggestion = S["CompanySuggestion"];
export type CompanySearchRequest = S["CompanySearchRequest"];
export type LocalCompanySearchRequest = S["LocalCompanySearchRequest"];
export type SimilarCompaniesRequest = S["SimilarCompaniesRequest"];
export type TargetCompanyOut = S["TargetCompanyOut"];
export type TargetCompanyCreate = S["TargetCompanyCreate"];

export type SkillSuggestion = S["SkillSuggestion"];
export type CVParseResult = S["CVParseResult"];
export type CVExtractedProfile = S["CVExtractedProfile"];
export type CVExperienceExtract = S["CVExperienceExtract"];
export type CVEducationExtract = S["CVEducationExtract"];
export type CustomCvRequest = S["CustomCvRequest"];
export type IntelligenceReportOut = S["IntelligenceReportOut"];
