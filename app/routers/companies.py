"""
Router: aziende target — RF2.2, RF2.3

L'endpoint /similar riceve la lista CUMULATIVA delle aziende selezionate:
è il meccanismo che rende progressivo il suggerimento (effetto Spotify).
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import verify_token
from app import models, schemas
from app.database import get_db
from app.routers.sessions import get_session_or_404
from app.services.company_discovery import CompanyDiscoveryEngine
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users/{user_id}/sessions/{session_id}/companies", tags=["Aziende"], dependencies=[Depends(verify_token)],)


# ---------------------------------------------------------------------
# RF2.2 — ricerca aziende
# ---------------------------------------------------------------------
@router.post("/search", response_model=list[schemas.CompanySuggestion])
async def search_companies(
    user_id: str,
    session_id: str,
    payload: schemas.CompanySearchRequest,
    db: Session = Depends(get_db),
):
    get_session_or_404(db, user_id, session_id)
    engine = CompanyDiscoveryEngine(LLMGateway(db=db))
    results = await engine.search_companies(
        payload.query, payload.location, payload.sector, payload.limit
    )
    return [schemas.CompanySuggestion(**r) for r in results]


@router.post("/search-local", response_model=list[schemas.CompanySuggestion])
async def search_local_companies(
    user_id: str,
    session_id: str,
    payload: schemas.LocalCompanySearchRequest,
    db: Session = Depends(get_db),
):
    """Caso 'voglio restare vicino casa' — Places trova anche le PMI
    che l'LLM non conosce."""
    get_session_or_404(db, user_id, session_id)
    engine = CompanyDiscoveryEngine(LLMGateway(db=db))
    results = await engine.search_local_companies(payload.sector, payload.area, payload.limit)
    return [schemas.CompanySuggestion(**r) for r in results]


# ---------------------------------------------------------------------
# RF2.3 — suggerimenti cumulativi (effetto Spotify)
# ---------------------------------------------------------------------
@router.post("/similar", response_model=list[schemas.CompanySuggestion])
async def suggest_similar(
    user_id: str,
    session_id: str,
    payload: schemas.SimilarCompaniesRequest,
    db: Session = Depends(get_db),
):
    """Riceve TUTTE le aziende selezionate finora, non solo l'ultima.
    Più selezioni → suggerimenti più mirati."""
    get_session_or_404(db, user_id, session_id)
    engine = CompanyDiscoveryEngine(LLMGateway(db=db))
    results = await engine.suggest_similar(
        payload.selected_companies, payload.location, payload.sector, payload.limit
    )
    return [schemas.CompanySuggestion(**r) for r in results]


# ---------------------------------------------------------------------
# CRUD aziende target della sessione
# ---------------------------------------------------------------------
@router.post("", response_model=schemas.TargetCompanyOut, status_code=201)
def add_company(
    user_id: str,
    session_id: str,
    payload: schemas.TargetCompanyCreate,
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user_id, session_id)
    existing = (
        db.query(models.TargetCompany)
        .filter(
            models.TargetCompany.session_id == session.id,
            models.TargetCompany.name.ilike(payload.name),
        )
        .first()
    )
    if existing:
        raise HTTPException(400, "Azienda già presente in questa sessione")

    company = models.TargetCompany(session_id=session.id, **payload.model_dump())
    db.add(company)

    # RF... — le aziende scelte per una ricerca finiscono anche tra i
    # "preferiti" del profilo, come suggerimento per ricerche future.
    # Silenzioso, dedup per nome: non deve mai far fallire l'aggiunta
    # dell'azienda alla sessione se qualcosa va storto qui.
    try:
        already_preferred = (
            db.query(models.UserPreferredCompany)
            .filter(
                models.UserPreferredCompany.user_id == user_id,
                models.UserPreferredCompany.name.ilike(payload.name),
            )
            .first()
        )
        if not already_preferred:
            db.add(models.UserPreferredCompany(
                user_id=user_id,
                name=payload.name,
                country=payload.country,
                size=payload.size,
                sector=payload.sector,
                website=payload.website,
                source=payload.source,
            ))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Salvataggio azienda preferita fallito per %s: %s", payload.name, exc)

    db.commit()
    db.refresh(company)
    return company


@router.get("", response_model=list[schemas.TargetCompanyOut])
def list_companies(user_id: str, session_id: str, db: Session = Depends(get_db)):
    session = get_session_or_404(db, user_id, session_id)
    return session.companies


@router.delete("/{company_id}", status_code=204)
def delete_company(
    user_id: str, session_id: str, company_id: str, db: Session = Depends(get_db)
):
    get_session_or_404(db, user_id, session_id)
    company = db.get(models.TargetCompany, company_id)
    if not company or company.session_id != session_id:
        raise HTTPException(404, "Azienda non trovata")
    db.delete(company)
    db.commit()
