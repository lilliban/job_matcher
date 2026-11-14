"""
Router: creazione del profilo — a mano oppure dal CV.

Il percorso dal CV è in due tempi, entrambi prima che esista un utente:
  1. POST /parse-cv  — estrae i dati dal PDF e li restituisce. Non scrive nulla.
  2. POST /create    — riceve i dati GIÀ RIVISTI dall'utente (l'estrazione
                       dell'LLM può sbagliare) e crea utente, competenze,
                       lingue, esperienze, formazione e CV base in un'unica
                       transazione.

Il percorso a mano usa solo /create con nome ed email: le altre sezioni si
compilano dopo, una per una.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app import models, schemas
from app.core.security import verify_token
from app.database import get_db
from app.services.cv_parser import CVParser
from app.services.llm_gateway import LLMGateway, LLMGatewayError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/onboarding",
    tags=["Creazione profilo"],
    dependencies=[Depends(verify_token)],
)

MAX_CV_SIZE = 8 * 1024 * 1024


class ProfileDraft(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    hard_skills: list[str] = []
    soft_skills: list[str] = []
    languages: list[dict] = []
    experiences: list[schemas.CVExperienceExtract] = []
    education: list[schemas.CVEducationExtract] = []
    # testo del CV: se presente diventa il CV base da cui si adattano i
    # documenti per ogni annuncio. Assente nel percorso a mano.
    cv_text: Optional[str] = None


@router.post("/parse-cv")
async def parse_cv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    is_pdf = file.content_type == "application/pdf" or (
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
            "Il PDF non contiene testo leggibile (probabilmente è una scansione). "
            "Prova con un PDF esportato da Word o Google Docs, oppure compila a mano.",
        )

    try:
        profile = await parser.extract_profile(raw_text)
    except LLMGatewayError as exc:
        raise HTTPException(503, str(exc)) from exc
    critique = await parser.critique(raw_text)

    return {"profile": profile, "critique": critique, "cv_text": raw_text}


@router.post("/create", response_model=schemas.UserOut, status_code=201)
def create_profile(draft: ProfileDraft, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.email == draft.email).first():
        raise HTTPException(400, "Esiste già un profilo con questa email")

    user = models.User(
        name=draft.name.strip(),
        email=draft.email,
        phone=draft.phone or None,
        location=draft.location or None,
        bio=draft.bio or None,
    )
    db.add(user)
    db.flush()

    seen: set[str] = set()
    for name in draft.hard_skills:
        name = (name or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            db.add(models.UserHardSkill(user_id=user.id, name=name))

    seen = set()
    for name in draft.soft_skills:
        name = (name or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            db.add(models.SoftSkill(user_id=user.id, name=name))

    for lang in draft.languages:
        language = str(lang.get("language") or "").strip().lower()
        if not language:
            continue
        level = str(lang.get("level") or "B1").strip()
        native = level.lower() in ("madrelingua", "native")
        db.add(models.UserLanguage(
            user_id=user.id, language=language,
            level="madrelingua" if native else level.upper(), is_native=native,
        ))

    for e in draft.experiences:
        if e.company and e.role:
            db.add(models.Experience(
                user_id=user.id, company=e.company, role=e.role,
                start_date=e.start_date, end_date=e.end_date,
                description=e.description,
            ))

    for ed in draft.education:
        if ed.institution:
            db.add(models.Education(
                user_id=user.id, institution=ed.institution, degree=ed.degree,
                field=ed.field, year=ed.year,
            ))

    if draft.cv_text and draft.cv_text.strip():
        db.add(models.BaseDocument(
            user_id=user.id, doc_type="cv", content=draft.cv_text, source="uploaded",
        ))

    db.commit()
    db.refresh(user)
    return user
