"""
Modelli ORM — corrispondono al DomainModel del file job_matcher.xmi.

Distinzione chiave (decisa in fase di design):
  - USER_HARD_SKILL  -> cosa SA fare il candidato
  - SESSION_HARD_SKILL -> cosa RICHIEDE il ruolo target
  Il matching confronta le due.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """datetime.utcnow() è deprecato in 3.12 — questa è la versione corretta."""
    return datetime.now(timezone.utc)


# =====================================================================
# PROFILO UTENTE
# =====================================================================
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    location = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    personal_phrase = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    soft_skills = relationship("SoftSkill", back_populates="user", cascade="all, delete-orphan")
    hard_skills = relationship("UserHardSkill", back_populates="user", cascade="all, delete-orphan")
    experiences = relationship("Experience", back_populates="user", cascade="all, delete-orphan")
    education = relationship("Education", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("SearchSession", back_populates="user", cascade="all, delete-orphan")
    preferred_companies = relationship("UserPreferredCompany", back_populates="user", cascade="all, delete-orphan")
    base_documents = relationship("BaseDocument", back_populates="user", cascade="all, delete-orphan")
    collections = relationship("CompanyCollection", back_populates="user", cascade="all, delete-orphan")
    years_experience_total = Column(Integer, default=0)  
    work_mode_pref = Column(String, nullable=True) 
    contract_type_pref = Column(String, nullable=True)  
    min_salary = Column(Integer, nullable=True)
    max_annuncio_age_days = Column(Integer, default=30) 
    
    languages = relationship("UserLanguage", back_populates="user", cascade="all, delete-orphan")

class SoftSkill(Base):
    """RF1.2 — le soft skill appartengono alla PERSONA, non alla sessione."""

    __tablename__ = "soft_skills"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)

    user = relationship("User", back_populates="soft_skills")


class UserHardSkill(Base):
    """Cosa SA fare il candidato — indipendente da dove l'ha imparato."""

    __tablename__ = "user_hard_skills"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    level = Column(String, default="intermediate")  # beginner/intermediate/expert
    years_exp = Column(Integer, default=0)
    acquired_via = Column(String, nullable=True)  # work/university/self_taught/certification

    user = relationship("User", back_populates="hard_skills")

class UserLanguage(Base):
    """Lingue conosciute dall'utente con livello CEFR."""
    __tablename__ = "user_languages"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    language = Column(String, nullable=False)  # italian/english/german/french/spanish
    level = Column(String, default="B1")  # madrelingua/A1/A2/B1/B2/C1/C2
    is_native = Column(Boolean, default=False)

    user = relationship("User", back_populates="languages")

class Experience(Base):
    """Dove HA lavorato — separata dalle skill (decisione di design)."""

    __tablename__ = "experiences"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    skills_used = Column(Text, nullable=True)  # JSON list — arricchisce la generazione CV

    user = relationship("User", back_populates="experiences")



class Education(Base):
    __tablename__ = "education"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    institution = Column(String, nullable=False)
    degree = Column(String, nullable=True)
    field = Column(String, nullable=True)
    year = Column(String, nullable=True)

    user = relationship("User", back_populates="education")


class BaseDocument(Base):
    """CV e lettera "generali" dell'utente, da cui derivano le versioni per
    singolo annuncio.

    Prima ogni documento veniva generato da zero dal profilo grezzo, per
    ogni match: tre chiamate LLM per annuncio, e nessuna coerenza tra un
    CV e l'altro. Con un documento base il testo per l'azienda diventa un
    ADATTAMENTO — prompt più corto e risultato più coerente.

    È anche la risposta alla bio scritta a mano: il campo `User.bio` non
    sparisce (lo leggono il matching semantico e il generatore di
    documenti) ma smette di essere qualcosa che l'utente compila, e viene
    derivato una volta dal CV caricato."""

    __tablename__ = "base_documents"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    doc_type = Column(String, nullable=False)  # cv/cover_letter
    content = Column(Text, nullable=True)
    source = Column(String, default="generated")  # uploaded/generated/edited
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    user = relationship("User", back_populates="base_documents")

    __table_args__ = (Index("ix_base_doc_user_type", "user_id", "doc_type"),)


class UserPreferredCompany(Base):
    """Aziende che interessano alla PERSONA, non a una ricerca specifica —
    stessa forma di TargetCompany ma a livello di profilo. Popolata in
    automatico quando l'utente aggiunge un'azienda target a una sessione
    (dedup per nome); proposta come suggerimento nelle ricerche future,
    non condivisa a forza tra sessioni con ruoli diversi (decisione di
    design — vedi docs/DECISIONS.md)."""

    __tablename__ = "user_preferred_companies"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    size = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    website = Column(String, nullable=True)
    source = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="preferred_companies")

    __table_args__ = (Index("ix_preferred_company_user_name", "user_id", "name"),)


class CompanyCollection(Base):
    """Una lista di aziende che l'utente cura nel tempo — la "bacheca".

    Differenza rispetto a UserPreferredCompany, che è una lista unica e
    piatta: qui le aziende si raggruppano per tema ("tech marchigiane",
    "brand di lusso") e da ogni gruppo si possono cercare simili. È il
    gruppo intero a fare da riferimento, non la singola azienda.

    Una collezione si APPLICA a una ricerca copiandone i membri in
    TargetCompany. Copia e non riferimento: una ricerca è un fatto
    storico, e non deve cambiare sotto i piedi se mesi dopo si modifica la
    collezione da cui era partita."""

    __tablename__ = "company_collections"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    # profilo della collezione riassunto dall'LLM una volta e riusato come
    # contesto: con decine di aziende, rielencarle tutte a ogni richiesta
    # di simili farebbe crescere il prompt senza limite (ADR-005)
    profile_summary = Column(Text, nullable=True)
    profile_summary_size = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="collections")
    members = relationship(
        "CompanyCollectionMember", back_populates="collection",
        cascade="all, delete-orphan",
    )


class CompanyCollectionMember(Base):
    __tablename__ = "company_collection_members"

    id = Column(String, primary_key=True, default=gen_id)
    collection_id = Column(String, ForeignKey("company_collections.id"), nullable=False)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    size = Column(String, nullable=True)
    website = Column(String, nullable=True)
    added_via = Column(String, default="manual")  # manual/similar/theme/places
    created_at = Column(DateTime, default=utcnow)

    collection = relationship("CompanyCollection", back_populates="members")

    __table_args__ = (Index("ix_collection_member_name", "collection_id", "name"),)


# =====================================================================
# REGISTRO AZIENDE GLOBALE
# =====================================================================
class CompanyProfile(Base):
    """Ciò che si sa di un'azienda a prescindere da chi la cerca e quando.

    Nasce da un problema misurato: `careers_url` viveva solo su
    TargetCompany, che è legata a una sessione. Trovarlo costa fino a 8
    richieste HTTP in sequenza, e veniva rifatto da zero a ogni nuova
    ricerca — anche per la stessa identica azienda cercata il giorno prima.

    Qui i dati costosi da scoprire (careers page, provider ATS, slug) si
    scoprono una volta e valgono per sempre. `ats_probed_at` viene
    valorizzato anche quando la ricerca dell'ATS fallisce: sapere che
    un'azienda NON ha un ATS pubblico è un risultato utile quanto il
    contrario, e va ricordato per non riprovare a ogni ricerca."""

    __tablename__ = "company_profiles"

    id = Column(String, primary_key=True, default=gen_id)
    # nome normalizzato (lowercase, spazi compattati) — la chiave con cui
    # si riconosce la stessa azienda scritta in modi leggermente diversi
    name_key = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    country_code = Column(String, nullable=True)

    careers_url = Column(String, nullable=True)
    careers_url_verified = Column(Boolean, default=False)

    # greenhouse/lever/ashby/smartrecruiters/workable/recruitee/personio
    ats_provider = Column(String, nullable=True)
    ats_slug = Column(String, nullable=True)
    ats_probed_at = Column(DateTime, nullable=True)
    ats_probe_failed = Column(Boolean, default=False)

    last_fetched_at = Column(DateTime, nullable=True)
    consecutive_fetch_failures = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)


# =====================================================================
# SESSIONE DI RICERCA
# =====================================================================
class SearchSession(Base):
    __tablename__ = "search_sessions"

    id = Column(String, primary_key=True, default=gen_id)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role_title = Column(String, nullable=False)
    status = Column(String, default="draft")  # draft/running/completed/error/cancelled
    # preferred_country accetta sia uno stato ("IT") sia un continente
    # ("EU"); location_pref è la zona in chiaro. Restano entrambi perché le
    # sessioni già nel database li usano e la ricerca li legge ancora: i
    # campi geo_* sotto sono la forma strutturata, derivata da questi.
    preferred_country = Column(String, nullable=True)
    location_pref = Column(String, nullable=True)
    geo_scope = Column(String, nullable=True)    # continent/country/region
    geo_country = Column(String, nullable=True)  # codice stato, anche dentro un continente
    geo_region = Column(String, nullable=True)   # regione scelta dall'elenco
    contract_type = Column(String, nullable=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    match_threshold = Column(Float, default=0.5)
    created_at = Column(DateTime, default=utcnow)
    last_run_at = Column(DateTime, nullable=True)

    # progresso della run corrente — alimenta il polling del frontend (RF8.5)
    progress_current = Column(Integer, default=0)
    progress_total = Column(Integer, default=0)
    progress_message = Column(String, nullable=True)

    user = relationship("User", back_populates="sessions")
    hard_skills = relationship("SessionHardSkill", back_populates="session", cascade="all, delete-orphan")
    companies = relationship("TargetCompany", back_populates="session", cascade="all, delete-orphan")
    listings = relationship("JobListing", back_populates="session", cascade="all, delete-orphan")
    logs = relationship("SearchLog", back_populates="session", cascade="all, delete-orphan")
    matches = relationship("Match", back_populates="session", cascade="all, delete-orphan")


class SessionHardSkill(Base):
    """RF2.1 — cosa RICHIEDE il ruolo target, non cosa sa l'utente."""

    __tablename__ = "session_hard_skills"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("search_sessions.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    required = Column(Boolean, default=True)
    min_years = Column(Integer, default=0)

    session = relationship("SearchSession", back_populates="hard_skills")


class TargetCompany(Base):
    """RF2.2 — aziende target. careers_url trovato dinamicamente (RF3.1b)."""

    __tablename__ = "target_companies"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("search_sessions.id"), nullable=False)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    size = Column(String, nullable=True)
    sector = Column(String, nullable=True)
    website = Column(String, nullable=True)
    careers_url = Column(String, nullable=True)
    careers_url_verified = Column(Boolean, default=False)
    source = Column(String, nullable=True)  # manual/llm/places/similar
    # RF3.5 — se l'azienda suggerita dall'LLM non esiste online viene scartata
    exists_online = Column(Boolean, default=True)

    # collegamento al registro globale: careers_url e provider ATS si
    # scoprono una volta sola lì, non a ogni sessione (vedi CompanyProfile)
    company_profile_id = Column(String, ForeignKey("company_profiles.id"), nullable=True)

    # stato dell'ultima ricerca su questa azienda — alimenta la vista della
    # ricerca aperta e permette al re-run di saltare ciò che è ancora fresco
    last_searched_at = Column(DateTime, nullable=True)
    last_result = Column(String, nullable=True)  # found/no_openings/unreachable
    last_postings_count = Column(Integer, nullable=True)

    session = relationship("SearchSession", back_populates="companies")
    profile = relationship("CompanyProfile")


class JobPosting(Base):
    """L'annuncio in sé, indipendente da chi l'ha cercato.

    Prima esisteva solo JobListing, legata a una sessione: due ricerche
    sulla stessa azienda raccoglievano due volte gli stessi annunci, con
    due volte le richieste di rete e due volte il costo di estrazione.
    Qui l'annuncio vive una volta sola, identificato da content_hash, e le
    sessioni ci si agganciano.

    I campi normalizzati esistono per poter filtrare SENZA chiamare un LLM.
    Vengono riempiti in ordine di costo: dal JSON dell'ATS dove il dato è
    già strutturato (gratis), altrimenti con regex sul testo (gratis).
    Sono best-effort per costruzione — un annuncio raccolto via scraping
    HTML ha la sede scritta in linguaggio naturale, e a volte non ce l'ha
    affatto: vanno letti come indizi, non come verità.
    """

    __tablename__ = "job_postings"

    id = Column(String, primary_key=True, default=gen_id)
    content_hash = Column(String, nullable=False, unique=True, index=True)

    title = Column(String, nullable=False)
    company_name = Column(String, nullable=False, index=True)
    source_url = Column(String, nullable=True)
    source_board = Column(String, nullable=True)
    source_kind = Column(String, nullable=True)  # ats/board/careers

    description = Column(Text, nullable=True)
    requirements_raw = Column(Text, nullable=True)
    location = Column(String, nullable=True)

    # --- campi normalizzati, per filtrare senza LLM ---
    contract_type = Column(String, nullable=True)       # testo originale
    contract_type_norm = Column(String, nullable=True)  # full_time/part_time/...
    work_mode = Column(String, nullable=True)           # remote/hybrid/onsite
    seniority = Column(String, nullable=True)
    department = Column(String, nullable=True)
    min_years_exp = Column(Integer, nullable=True)
    max_years_exp = Column(Integer, nullable=True)
    languages = Column(Text, nullable=True)             # JSON list
    city = Column(String, nullable=True)
    country_code = Column(String, nullable=True, index=True)
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String, nullable=True)
    posted_date = Column(String, nullable=True)

    # --- ciclo di vita ---
    # Una posizione si considera chiusa quando due letture COMPLETE e
    # consecutive del feed della sua azienda non la restituiscono più.
    # Si guarda la presenza nel feed, non le date di scadenza dichiarate:
    # quelle sono spesso assenti o sbagliate.
    first_seen_at = Column(DateTime, default=utcnow)
    last_seen_at = Column(DateTime, default=utcnow)
    consecutive_misses = Column(Integer, default=0)
    is_closed = Column(Boolean, default=False)

    listings = relationship("JobListing", back_populates="posting")


class JobListing(Base):
    """La comparsa di un annuncio dentro una ricerca specifica.

    Le colonne di contenuto restano duplicate da JobPosting di proposito:
    la vista Risultati e i Match esistenti le leggono da qui, e riscriverli
    tutti per un guadagno di normalizzazione avrebbe messo a rischio dati
    reali già in produzione (ADR-020)."""

    __tablename__ = "job_listings"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("search_sessions.id"), nullable=False)
    posting_id = Column(String, ForeignKey("job_postings.id"), nullable=True)
    title = Column(String, nullable=False)
    company_name = Column(String, nullable=False)
    source_url = Column(String, nullable=True)
    source_board = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    requirements_raw = Column(Text, nullable=True)
    location = Column(String, nullable=True)
    contract_type = Column(String, nullable=True)
    posted_date = Column(String, nullable=True)
    is_expired = Column(Boolean, default=False)
    # RF3.4 — deduplicazione per hash del contenuto
    content_hash = Column(String, nullable=True, index=True)
    scraped_at = Column(DateTime, default=utcnow)

    session = relationship("SearchSession", back_populates="listings")
    posting = relationship("JobPosting", back_populates="listings")
    matches = relationship("Match", back_populates="listing", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_listing_session_hash", "session_id", "content_hash"),)


class Match(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("search_sessions.id"), nullable=False)
    listing_id = Column(String, ForeignKey("job_listings.id"), nullable=False)
    score = Column(Float, default=0.0)
    keyword_score = Column(Float, default=0.0)
    semantic_score = Column(Float, default=0.0)
    matched_skills = Column(Text, nullable=True)  # JSON
    missing_skills = Column(Text, nullable=True)  # JSON
    gap_analysis = Column(Text, nullable=True)
    # RF6.1 — tracking candidature
    status = Column(String, default="new")  # new/saved/applied/interview/rejected/discarded
    created_at = Column(DateTime, default=utcnow)

    session = relationship("SearchSession", back_populates="matches")
    listing = relationship("JobListing", back_populates="matches")
    documents = relationship("GeneratedDocument", back_populates="match", cascade="all, delete-orphan")


class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id = Column(String, primary_key=True, default=gen_id)
    match_id = Column(String, ForeignKey("matches.id"), nullable=False)
    doc_type = Column(String, nullable=False)  # cv/cover_letter/email
    content = Column(Text, nullable=True)
    llm_model = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    match = relationship("Match", back_populates="documents")


class SearchLog(Base):
    """RF8 — alimenta la Pagina Intelligence e il log live."""

    __tablename__ = "search_logs"

    id = Column(String, primary_key=True, default=gen_id)
    session_id = Column(String, ForeignKey("search_sessions.id"), nullable=False)
    source = Column(String, nullable=True)
    action = Column(String, nullable=True)
    result = Column(String, nullable=True)
    level = Column(String, default="info")  # info/warning/error
    ts = Column(DateTime, default=utcnow)

    session = relationship("SearchSession", back_populates="logs")


# =====================================================================
# RNF2 — Cache LLM
# =====================================================================
class LLMCache(Base):
    """Stessa coppia (prompt_hash, model) non viene rielaborata.
    Fondamentale per non esaurire il free tier di Gemini."""

    __tablename__ = "llm_cache"

    id = Column(String, primary_key=True, default=gen_id)
    prompt_hash = Column(String, nullable=False, index=True, unique=True)
    model = Column(String, nullable=False)
    response = Column(Text, nullable=False)
    hit_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)
