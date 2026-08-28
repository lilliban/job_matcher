"""
Schemi Pydantic — validazione request/response.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# =====================================================================
# User
# =====================================================================
class UserBase(BaseModel):
    name: str
    email: EmailStr
    location: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    years_experience_total: Optional[int] = None
    work_mode_pref: Optional[str] = None
    contract_type_pref: Optional[str] = None
    min_salary: Optional[int] = None
    max_annuncio_age_days: Optional[int] = None

class UserLanguageCreate(BaseModel):
    language: str
    level: str = "B1"
    is_native: bool = False

class UserLanguageOut(UserLanguageCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    
class CustomCvRequest(BaseModel):
    url: str    
    
class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


# =====================================================================
# Skills
# =====================================================================
class SoftSkillCreate(BaseModel):
    name: str
    category: Optional[str] = None


class SoftSkillOut(SoftSkillCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


class UserHardSkillCreate(BaseModel):
    name: str
    category: Optional[str] = None
    level: str = "intermediate"
    years_exp: int = 0
    acquired_via: Optional[str] = None


class UserHardSkillOut(UserHardSkillCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


class UserHardSkillUpdate(BaseModel):
    category: Optional[str] = None
    level: Optional[str] = None
    years_exp: Optional[int] = None
    acquired_via: Optional[str] = None


class SessionHardSkillCreate(BaseModel):
    name: str
    category: Optional[str] = None
    required: bool = True
    min_years: int = 0


class SessionHardSkillOut(SessionHardSkillCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str


# =====================================================================
# Experience / Education
# =====================================================================
class ExperienceCreate(BaseModel):
    company: str
    role: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    skills_used: Optional[str] = None


class ExperienceOut(ExperienceCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


class EducationCreate(BaseModel):
    institution: str
    degree: Optional[str] = None
    field: Optional[str] = None
    year: Optional[str] = None


class EducationOut(EducationCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str


# =====================================================================
# Session
# =====================================================================
class SearchSessionCreate(BaseModel):
    role_title: str
    preferred_country: Optional[str] = None
    location_pref: Optional[str] = None
    geo_scope: Optional[str] = None
    geo_country: Optional[str] = None
    geo_region: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    match_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    # Competenze e aziende arrivano insieme alla ricerca, non dopo.
    # Prima il form creava la sessione e SOLO ALLORA mostrava questi due
    # blocchi: erano parte della definizione della ricerca, ma l'ordine
    # imposto all'utente diceva il contrario. Nessun vincolo tecnico lo
    # richiedeva — gli endpoint di scoperta non usano la sessione.
    hard_skills: list[str] = Field(default_factory=list)
    companies: list["TargetCompanyCreate"] = Field(default_factory=list)


class SearchSessionUpdate(BaseModel):
    role_title: Optional[str] = None
    preferred_country: Optional[str] = None
    location_pref: Optional[str] = None
    geo_scope: Optional[str] = None
    geo_country: Optional[str] = None
    geo_region: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    match_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SearchSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    role_title: str
    status: str
    preferred_country: Optional[str] = None
    location_pref: Optional[str] = None
    geo_scope: Optional[str] = None
    geo_country: Optional[str] = None
    geo_region: Optional[str] = None
    contract_type: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    match_threshold: float
    created_at: datetime
    last_run_at: Optional[datetime] = None
    progress_current: int = 0
    progress_total: int = 0
    progress_message: Optional[str] = None


class SessionStatusOut(BaseModel):
    """Risposta del polling durante la run."""
    session_id: str
    status: str
    progress_current: int
    progress_total: int
    progress_message: Optional[str] = None
    matches_found: int


# =====================================================================
# Companies
# =====================================================================
class CompanySearchRequest(BaseModel):
    query: str
    location: Optional[str] = None
    sector: Optional[str] = None
    limit: int = Field(default=8, ge=1, le=20)


class LocalCompanySearchRequest(BaseModel):
    sector: str
    area: str
    limit: int = Field(default=10, ge=1, le=20)


class SimilarCompaniesRequest(BaseModel):
    """RF2.3 — effetto Spotify: si passa la lista CUMULATIVA."""
    selected_companies: list[str]
    location: Optional[str] = None
    sector: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=10)


class CompanySuggestion(BaseModel):
    name: str
    sector: Optional[str] = None
    size: Optional[str] = None
    # codice paese ISO ("IT"), non una zona e non un indirizzo — vedi
    # CompanyDiscoveryEngine._verify_and_enrich
    country: Optional[str] = None
    # indirizzo completo restituito da Google Places, quando configurata:
    # sta in un campo suo proprio invece di sovrascrivere `country`
    address: Optional[str] = None
    website: Optional[str] = None
    source: Optional[str] = None
    exists_online: bool = True
    reason: Optional[str] = None


class TargetCompanyCreate(BaseModel):
    name: str
    country: Optional[str] = None
    size: Optional[str] = None
    sector: Optional[str] = None
    website: Optional[str] = None
    source: str = "manual"


class TargetCompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    name: str
    country: Optional[str] = None
    size: Optional[str] = None
    sector: Optional[str] = None
    website: Optional[str] = None
    careers_url: Optional[str] = None
    careers_url_verified: bool
    source: Optional[str] = None
    exists_online: bool
    last_searched_at: Optional[datetime] = None
    last_result: Optional[str] = None
    last_postings_count: Optional[int] = None


# =====================================================================
# Aziende preferite (profilo — non legate a una sessione specifica)
# =====================================================================
class PreferredCompanyCreate(BaseModel):
    name: str
    country: Optional[str] = None
    size: Optional[str] = None
    sector: Optional[str] = None
    website: Optional[str] = None
    source: Optional[str] = None


class PreferredCompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    name: str
    country: Optional[str] = None
    size: Optional[str] = None
    sector: Optional[str] = None
    website: Optional[str] = None
    source: Optional[str] = None


# =====================================================================
# Listings / Matches
# =====================================================================
class JobListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    title: str
    company_name: str
    source_url: Optional[str] = None
    source_board: Optional[str] = None
    description: Optional[str] = None
    requirements_raw: Optional[str] = None
    location: Optional[str] = None
    contract_type: Optional[str] = None
    posted_date: Optional[str] = None
    is_expired: bool
    scraped_at: datetime


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    listing_id: str
    score: float
    keyword_score: float
    semantic_score: float
    matched_skills: Optional[str] = None
    missing_skills: Optional[str] = None
    gap_analysis: Optional[str] = None
    status: str
    created_at: datetime


class MatchDetailOut(MatchOut):
    listing: Optional[JobListingOut] = None
    documents: list["GeneratedDocumentOut"] = []


class MatchStatusUpdate(BaseModel):
    status: str = Field(description="new/saved/applied/interview/rejected/discarded")


# =====================================================================
# Documents
# =====================================================================
class GeneratedDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    match_id: str
    doc_type: str
    content: Optional[str] = None
    llm_model: Optional[str] = None
    created_at: datetime


class DocumentRegenerateRequest(BaseModel):
    doc_type: str = Field(description="cv/cover_letter/email")
    extra_instructions: Optional[str] = None


# =====================================================================
# Logs / Intelligence (RF8)
# =====================================================================
class SearchLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    source: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    level: str
    ts: datetime


class CompanyOutcome(BaseModel):
    """RF8.2 — perché questa azienda non ha prodotto match."""
    company: str
    listings_found: int
    matches_found: int
    reason: str


class AlternativeRole(BaseModel):
    """RF8.4"""
    role: str
    overlap: Optional[str] = None
    why: Optional[str] = None


class IntelligenceReportOut(BaseModel):
    """RF8 — la Pagina Intelligence."""
    session_id: str
    role_title: str
    status: str
    sources_queried: int
    total_companies: int
    companies_verified: int
    total_listings: int
    total_matches: int
    avg_score: float
    best_score: float
    top_missing_skills: list[dict[str, Any]]
    company_outcomes: list[CompanyOutcome]
    alternative_roles: list[AlternativeRole]
    summary: Optional[str] = None


# =====================================================================
# Skill suggestion (RF2.1)
# =====================================================================
class SkillSuggestion(BaseModel):
    name: str
    category: Optional[str] = None
    importance: Optional[str] = None


# =====================================================================
# Import CV (RF... upload PDF)
# =====================================================================
class CVExperienceExtract(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class CVEducationExtract(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    year: Optional[str] = None


class CVExtractedProfile(BaseModel):
    """Dati letti dal CV — mai scritti automaticamente: il frontend li
    mostra in una schermata di revisione e l'utente sceglie cosa applicare."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    hard_skills: list[str] = []
    soft_skills: list[str] = []
    languages: list[dict] = []
    experiences: list[CVExperienceExtract] = []
    education: list[CVEducationExtract] = []


class CVParseResult(BaseModel):
    profile: CVExtractedProfile
    critique: Optional[str] = None


MatchDetailOut.model_rebuild()


# =====================================================================
# Collezioni di aziende (bacheche)
# =====================================================================
class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CollectionOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    profile_summary: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CollectionMemberCreate(BaseModel):
    name: str
    country: Optional[str] = None
    sector: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    added_via: str = "manual"


class CollectionMemberOut(BaseModel):
    id: str
    name: str
    country: Optional[str] = None
    sector: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    added_via: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CollectionSimilarRequest(BaseModel):
    limit: int = 8
    country_code: Optional[str] = None


class ThemeSearchRequest(BaseModel):
    theme: str
    location: Optional[str] = None
    country_code: Optional[str] = None
    limit: int = 8


# =====================================================================
# Documenti base (CV / lettera generali dell'utente)
# =====================================================================
class BaseDocumentIn(BaseModel):
    content: str
    source: str = "edited"


class BaseDocumentOut(BaseModel):
    id: str
    doc_type: str
    content: Optional[str] = None
    source: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
