"""
Router: profilo utente — RF1.1, RF1.2, UC01–UC05
"""
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.core.security import verify_token
from app import models, schemas
from app.database import get_db
from app.services.cv_parser import CVParser
from app.services.llm_gateway import LLMGateway, LLMGatewayError
from app.services.scraper import ScraperEngine
from app.services.doc_generator import DocumentGenerator
from app.services.matcher import MatchingEngine

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users",
    tags=["Profilo"],
    dependencies=[Depends(verify_token)],
)

MAX_CV_SIZE = 8 * 1024 * 1024  # 8MB — un CV in PDF normale è molto più piccolo


def get_user_or_404(db: Session, user_id: str) -> models.User:
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")
    return user

def _build_user_profile_from_db(user: models.User) -> dict:
    """Costruisce il profilo utente per il generatore di documenti."""
    return {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "location": user.location,
        "bio": user.bio,
        "soft_skills": [s.name for s in user.soft_skills],
        "hard_skills": [
            {
                "name": s.name,
                "level": s.level,
                "years_exp": s.years_exp,
                "acquired_via": s.acquired_via,
            }
            for s in user.hard_skills
        ],
        "experiences": [
            {
                "company": e.company,
                "role": e.role,
                "start_date": e.start_date,
                "end_date": e.end_date,
                "description": e.description,
                "skills_used": e.skills_used,
            }
            for e in user.experiences
        ],
        "education": [
            {
                "institution": e.institution,
                "degree": e.degree,
                "field": e.field,
                "year": e.year,
            }
            for e in user.education
        ],
        "base_documents": {
            d.doc_type: d.content for d in user.base_documents if d.content
        },
        "languages": [
            {
                "language": lang.language,
                "level": lang.level,
                "is_native": lang.is_native,
            }
            for lang in user.languages
        ],
        "years_experience_total": user.years_experience_total or 0,
        "work_mode_pref": user.work_mode_pref,
        "contract_type_pref": user.contract_type_pref,
        "min_salary": user.min_salary,
    }
# ---------------------------------------------------------------------
# UC01 — profilo
# ---------------------------------------------------------------------
@router.post("", response_model=schemas.UserOut, status_code=201)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(400, "Esiste già un utente con questa email")
    user = models.User(**payload.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()


@router.get("/{user_id}", response_model=schemas.UserOut)
def get_user(user_id: str, db: Session = Depends(get_db)):
    return get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=schemas.UserOut)
def update_user(user_id: str, payload: schemas.UserUpdate, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    db.delete(user)
    db.commit()

@router.post("/{user_id}/languages", response_model=schemas.UserLanguageOut, status_code=201)
def add_language(user_id: str, payload: schemas.UserLanguageCreate, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    lang = models.UserLanguage(user_id=user_id, **payload.model_dump())
    db.add(lang)
    db.commit()
    db.refresh(lang)
    return lang

@router.get("/{user_id}/languages", response_model=list[schemas.UserLanguageOut])
def list_languages(user_id: str, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return db.query(models.UserLanguage).filter(models.UserLanguage.user_id == user_id).all()

@router.delete("/{user_id}/languages/{lang_id}", status_code=204)
def delete_language(user_id: str, lang_id: str, db: Session = Depends(get_db)):
    lang = db.get(models.UserLanguage, lang_id)
    if not lang or lang.user_id != user_id:
        raise HTTPException(404, "Lingua non trovata")
    db.delete(lang)
    db.commit()
# ---------------------------------------------------------------------
# Import CV — RF... upload PDF, pre-compilazione con conferma dell'utente
# ---------------------------------------------------------------------
@router.post("/{user_id}/cv/parse", response_model=schemas.CVParseResult)
async def parse_cv(
    user_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Estrae dati strutturati + critica da un CV PDF. Non scrive NULLA sul
    profilo: il frontend mostra un'anteprima e l'utente conferma cosa
    applicare, tramite gli endpoint già esistenti (hard-skills/experiences/...)."""
    get_user_or_404(db, user_id)

    is_pdf = (file.content_type == "application/pdf") or (
        file.filename or ""
    ).lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(400, "Carica un file PDF")

    content = await file.read()
    if not content:
        raise HTTPException(400, "File vuoto")
    if len(content) > MAX_CV_SIZE:
        raise HTTPException(400, "File troppo grande (max 8MB)")

    parser = CVParser(LLMGateway(db=db))
    try:
        raw_text = parser.extract_text(content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Impossibile leggere il PDF: {exc}") from exc

    if len(raw_text) < 50:
        raise HTTPException(
            400,
            "Il PDF non contiene testo estraibile (probabilmente è una scansione "
            "immagine senza OCR)",
        )

    try:
        profile = await parser.extract_profile(raw_text)
    except LLMGatewayError as exc:
        raise HTTPException(503, str(exc)) from exc

    critique = await parser.critique(raw_text)  # None se l'LLM non risponde — non blocca l'estrazione

    # Il testo del CV diventa il CV BASE dell'utente: è il documento da cui
    # doc_generator deriva le versioni per singola azienda, invece di
    # riscriverne uno da zero dai dati grezzi per ogni annuncio.
    # Silenzioso: se fallisce non deve far perdere l'estrazione del profilo,
    # che è il motivo per cui l'utente ha caricato il file.
    try:
        base = (
            db.query(models.BaseDocument)
            .filter(
                models.BaseDocument.user_id == user_id,
                models.BaseDocument.doc_type == "cv",
            )
            .first()
        )
        if base is None:
            base = models.BaseDocument(user_id=user_id, doc_type="cv")
            db.add(base)
        base.content = raw_text
        base.source = "uploaded"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Salvataggio CV base fallito: %s", exc)
        db.rollback()

    return schemas.CVParseResult(profile=profile, critique=critique)

@router.post("/{user_id}/custom-cv")
async def generate_custom_cv(
    user_id: str,
    payload: schemas.CustomCvRequest,
    db: Session = Depends(get_db),
):
    """Genera CV, lettera e email partendo da un URL annuncio."""
    user = get_user_or_404(db, user_id)

    url = payload.url
    if not url:
        raise HTTPException(400, "URL mancante")

    llm = LLMGateway(db=db)
    scraper = ScraperEngine(llm)
    doc_gen = DocumentGenerator(llm)

    # 1. Estrai annunci dall'URL
    listings = await scraper.extract_listings_from_page(
        url,
        company_name="",
        source_board="manual_url",
    )

    if not listings:
        raise HTTPException(400, "Nessun annuncio trovato nell'URL")

    listing = listings[0]

    # 2. Profilo utente
    user_profile = _build_user_profile_from_db(user)
    user_skills = [s["name"] for s in user_profile["hard_skills"]]

    # 3. Calcola un tasso di compatibilità indicativo
    matcher = MatchingEngine(llm, user_profile=user_profile)
    
    # Estrai skill dai requisiti dell'annuncio per migliorare il match
    required_skills_from_listing = []
    requirements = (listing.get("requirements_raw") or listing.get("description") or "")
    # Cerca parole chiave comuni nel testo
    common_skills = ["python", "sql", "java", "javascript", "react", "angular", 
                     "machine learning", "deep learning", "data science", "ai", 
                     "cloud", "aws", "azure", "docker", "kubernetes", "git",
                     "ci/cd", "agile", "scrum", "leadership", "team management"]
    for skill in common_skills:
        if skill.lower() in requirements.lower():
            required_skills_from_listing.append(skill)
    
    match_result = await matcher.compute_score(
        user_skills=user_skills,
        required_skills=required_skills_from_listing,
        listing=listing,
        user_profile=user_profile,
    )

    # 4. Genera documenti
    documents = {}
    for doc_type in ("cv", "cover_letter", "email"):
        try:
            content = await doc_gen.generate(
                doc_type,
                user_profile,
                listing,
                match_result,
            )
            documents[doc_type] = content
        except Exception as exc:
            logger.warning("Generazione %s fallita: %s", doc_type, exc)
            documents[doc_type] = None

    return {
        "listing": listing,
        "score": match_result.get("score", 0.0),
        "keyword_score": match_result.get("keyword_score", 0.0),
        "semantic_score": match_result.get("semantic_score", 0.0),
        "matched_skills": match_result.get("matched_skills", "[]"),
        "missing_skills": match_result.get("missing_skills", "[]"),
        "gap_analysis": match_result.get("gap_analysis"),
        "documents": documents,
    }
# ---------------------------------------------------------------------
# UC02 — soft skill (legate all'utente, non alla sessione)
# ---------------------------------------------------------------------
@router.post("/{user_id}/soft-skills", response_model=schemas.SoftSkillOut, status_code=201)
def add_soft_skill(user_id: str, payload: schemas.SoftSkillCreate, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    skill = models.SoftSkill(user_id=user_id, **payload.model_dump())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.get("/{user_id}/soft-skills", response_model=list[schemas.SoftSkillOut])
def list_soft_skills(user_id: str, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return db.query(models.SoftSkill).filter(models.SoftSkill.user_id == user_id).all()


@router.delete("/{user_id}/soft-skills/{skill_id}", status_code=204)
def delete_soft_skill(user_id: str, skill_id: str, db: Session = Depends(get_db)):
    skill = db.get(models.SoftSkill, skill_id)
    if not skill or skill.user_id != user_id:
        raise HTTPException(404, "Soft skill non trovata")
    db.delete(skill)
    db.commit()


# ---------------------------------------------------------------------
# UC03 — hard skill dell'utente
# ---------------------------------------------------------------------
@router.post("/{user_id}/hard-skills", response_model=schemas.UserHardSkillOut, status_code=201)
def add_hard_skill(user_id: str, payload: schemas.UserHardSkillCreate, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    # dedup case-insensitive per nome (stesso pattern di add_preferred_company):
    # richiamare l'endpoint per una skill già presente non deve fallire — è il
    # caso normale quando una skill suggerita per un ruolo viene salvata anche
    # come competenza personale (vedi RF... skill suggerite -> profilo)
    existing = (
        db.query(models.UserHardSkill)
        .filter(
            models.UserHardSkill.user_id == user_id,
            models.UserHardSkill.name.ilike(payload.name),
        )
        .first()
    )
    if existing:
        return existing
    skill = models.UserHardSkill(user_id=user_id, **payload.model_dump())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.get("/{user_id}/hard-skills", response_model=list[schemas.UserHardSkillOut])
def list_hard_skills(user_id: str, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return db.query(models.UserHardSkill).filter(models.UserHardSkill.user_id == user_id).all()


@router.patch("/{user_id}/hard-skills/{skill_id}", response_model=schemas.UserHardSkillOut)
def update_hard_skill(
    user_id: str, skill_id: str, payload: schemas.UserHardSkillUpdate, db: Session = Depends(get_db)
):
    skill = db.get(models.UserHardSkill, skill_id)
    if not skill or skill.user_id != user_id:
        raise HTTPException(404, "Hard skill non trovata")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(skill, k, v)
    db.commit()
    db.refresh(skill)
    return skill


@router.delete("/{user_id}/hard-skills/{skill_id}", status_code=204)
def delete_hard_skill(user_id: str, skill_id: str, db: Session = Depends(get_db)):
    skill = db.get(models.UserHardSkill, skill_id)
    if not skill or skill.user_id != user_id:
        raise HTTPException(404, "Hard skill non trovata")
    db.delete(skill)
    db.commit()


# ---------------------------------------------------------------------
# UC04 — esperienze
# ---------------------------------------------------------------------
@router.post("/{user_id}/experiences", response_model=schemas.ExperienceOut, status_code=201)
def add_experience(user_id: str, payload: schemas.ExperienceCreate, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    exp = models.Experience(user_id=user_id, **payload.model_dump())
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


@router.get("/{user_id}/experiences", response_model=list[schemas.ExperienceOut])
def list_experiences(user_id: str, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return db.query(models.Experience).filter(models.Experience.user_id == user_id).all()


@router.delete("/{user_id}/experiences/{exp_id}", status_code=204)
def delete_experience(user_id: str, exp_id: str, db: Session = Depends(get_db)):
    exp = db.get(models.Experience, exp_id)
    if not exp or exp.user_id != user_id:
        raise HTTPException(404, "Esperienza non trovata")
    db.delete(exp)
    db.commit()


# ---------------------------------------------------------------------
# UC05 — formazione
# ---------------------------------------------------------------------
@router.post("/{user_id}/education", response_model=schemas.EducationOut, status_code=201)
def add_education(user_id: str, payload: schemas.EducationCreate, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    edu = models.Education(user_id=user_id, **payload.model_dump())
    db.add(edu)
    db.commit()
    db.refresh(edu)
    return edu


@router.get("/{user_id}/education", response_model=list[schemas.EducationOut])
def list_education(user_id: str, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return db.query(models.Education).filter(models.Education.user_id == user_id).all()


@router.delete("/{user_id}/education/{edu_id}", status_code=204)
def delete_education(user_id: str, edu_id: str, db: Session = Depends(get_db)):
    edu = db.get(models.Education, edu_id)
    if not edu or edu.user_id != user_id:
        raise HTTPException(404, "Titolo di studio non trovato")
    db.delete(edu)
    db.commit()


# ---------------------------------------------------------------------
# Aziende preferite — non legate a una sessione specifica, sono gli
# "obiettivi" della persona, suggerite come punto di partenza per
# nuove ricerche (vedi docs/DECISIONS.md)
# ---------------------------------------------------------------------
@router.post("/{user_id}/preferred-companies", response_model=schemas.PreferredCompanyOut, status_code=201)
def add_preferred_company(
    user_id: str, payload: schemas.PreferredCompanyCreate, db: Session = Depends(get_db)
):
    get_user_or_404(db, user_id)
    existing = (
        db.query(models.UserPreferredCompany)
        .filter(
            models.UserPreferredCompany.user_id == user_id,
            models.UserPreferredCompany.name.ilike(payload.name),
        )
        .first()
    )
    if existing:
        return existing
    company = models.UserPreferredCompany(user_id=user_id, **payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/{user_id}/preferred-companies", response_model=list[schemas.PreferredCompanyOut])
def list_preferred_companies(user_id: str, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return (
        db.query(models.UserPreferredCompany)
        .filter(models.UserPreferredCompany.user_id == user_id)
        .order_by(models.UserPreferredCompany.created_at.desc())
        .all()
    )


@router.delete("/{user_id}/preferred-companies/{company_id}", status_code=204)
def delete_preferred_company(user_id: str, company_id: str, db: Session = Depends(get_db)):
    company = db.get(models.UserPreferredCompany, company_id)
    if not company or company.user_id != user_id:
        raise HTTPException(404, "Azienda non trovata")
    db.delete(company)
    db.commit()
