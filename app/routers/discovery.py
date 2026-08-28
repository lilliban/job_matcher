"""
Router: ricerca aziende a livello UTENTE, senza sessione.

Perché esiste: gli stessi endpoint erano montati solo sotto
`/sessions/{session_id}/companies/...`, il che obbligava a creare una
ricerca prima di poter cercare aziende — ed è il motivo per cui competenze
e aziende target comparivano solo DOPO "Crea ricerca".

Verificato leggendo il codice: il `session_id` non arriva mai al motore.
`search_companies`, `search_local_companies` e `suggest_similar` non lo
ricevono e non lo usano; serviva solo a far passare `get_session_or_404`.
Quindi non c'era nessuna ragione tecnica per l'ordine imposto all'utente,
e non serve nemmeno una sessione "bozza": bastano gli stessi metodi esposti
un livello più su.

I vecchi endpoint restano dove sono e continuano a funzionare.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import schemas
from app.core.security import verify_token
from app.database import get_db
from app.services.collections import companies_by_theme
from app.services.company_discovery import CompanyDiscoveryEngine
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users/{user_id}/companies", tags=["Aziende"], dependencies=[Depends(verify_token)],)


def _engine(db: Session) -> CompanyDiscoveryEngine:
    return CompanyDiscoveryEngine(LLMGateway(db=db))


@router.post("/search", response_model=list[schemas.CompanySuggestion])
async def search_companies(
    user_id: str, payload: schemas.CompanySearchRequest, db: Session = Depends(get_db)
):
    results = await _engine(db).search_companies(
        payload.query, payload.location, payload.sector, payload.limit
    )
    return [schemas.CompanySuggestion(**r) for r in results]


@router.post("/search-local", response_model=list[schemas.CompanySuggestion])
async def search_local_companies(
    user_id: str, payload: schemas.LocalCompanySearchRequest, db: Session = Depends(get_db)
):
    results = await _engine(db).search_local_companies(
        payload.sector, payload.area, payload.limit
    )
    return [schemas.CompanySuggestion(**r) for r in results]


@router.post("/similar", response_model=list[schemas.CompanySuggestion])
async def suggest_similar(
    user_id: str, payload: schemas.SimilarCompaniesRequest, db: Session = Depends(get_db)
):
    results = await _engine(db).suggest_similar(
        payload.selected_companies, payload.location, payload.sector, payload.limit
    )
    return [schemas.CompanySuggestion(**r) for r in results]


@router.post("/by-theme", response_model=list[schemas.CompanySuggestion])
async def search_by_theme(
    user_id: str, payload: schemas.ThemeSearchRequest, db: Session = Depends(get_db)
):
    """Aziende per tema — "brand di lusso", "aziende sportive"…"""
    results = await companies_by_theme(
        _engine(db), payload.theme, location=payload.location,
        limit=payload.limit, country_code=payload.country_code,
    )
    return [schemas.CompanySuggestion(**r) for r in results]
