"""
Router: collezioni di aziende — le "bacheche".

L'idea è quella di Pinterest: si mette insieme un gruppo, e dal gruppo
intero si trovano simili. La differenza rispetto al suggerimento già
esistente (RF2.3, ADR-005) è che lì il riferimento era la lista di aziende
di UNA ricerca, e spariva con essa; qui la collezione vive nel profilo e
si riusa in tutte le ricerche future.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import verify_token
from app import models, schemas
from app.database import get_db
from app.services.collections import (
    COMPANY_THEMES,
    apply_to_session,
    collection_profile,
    suggest_for_collection,
)
from app.services.company_discovery import CompanyDiscoveryEngine
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users/{user_id}/collections", tags=["Collezioni"], dependencies=[Depends(verify_token)],)


def _get_or_404(db: Session, user_id: str, collection_id: str) -> models.CompanyCollection:
    coll = db.get(models.CompanyCollection, collection_id)
    if not coll or coll.user_id != user_id:
        raise HTTPException(404, "Collezione non trovata")
    return coll


@router.get("/themes")
def list_themes() -> list[dict]:
    """Temi predefiniti — "aziende tech", "brand di lusso", "sportive"…
    Sono scorciatoie per la ricerca libera, non un elenco chiuso."""
    return [{"key": k, "label": v["label"], "query": v["query"]}
            for k, v in COMPANY_THEMES.items()]


@router.post("", response_model=schemas.CollectionOut, status_code=201)
def create_collection(
    user_id: str, payload: schemas.CollectionCreate, db: Session = Depends(get_db)
):
    coll = models.CompanyCollection(
        user_id=user_id, name=payload.name, description=payload.description
    )
    db.add(coll)
    db.commit()
    db.refresh(coll)
    return coll


@router.get("", response_model=list[schemas.CollectionOut])
def list_collections(user_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.CompanyCollection)
        .filter(models.CompanyCollection.user_id == user_id)
        .order_by(models.CompanyCollection.created_at.desc())
        .all()
    )


@router.delete("/{collection_id}", status_code=204)
def delete_collection(user_id: str, collection_id: str, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, user_id, collection_id))
    db.commit()


@router.post("/{collection_id}/members", response_model=schemas.CollectionMemberOut, status_code=201)
def add_member(
    user_id: str, collection_id: str,
    payload: schemas.CollectionMemberCreate, db: Session = Depends(get_db),
):
    coll = _get_or_404(db, user_id, collection_id)
    existing = (
        db.query(models.CompanyCollectionMember)
        .filter(
            models.CompanyCollectionMember.collection_id == coll.id,
            models.CompanyCollectionMember.name.ilike(payload.name),
        )
        .first()
    )
    if existing:
        # ri-aggiungere un'azienda già presente non è un errore: è
        # esattamente quello che succede cliccando due volte un suggerimento
        return existing

    member = models.CompanyCollectionMember(collection_id=coll.id, **payload.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/{collection_id}/members", response_model=list[schemas.CollectionMemberOut])
def list_members(user_id: str, collection_id: str, db: Session = Depends(get_db)):
    return _get_or_404(db, user_id, collection_id).members


@router.delete("/{collection_id}/members/{member_id}", status_code=204)
def delete_member(
    user_id: str, collection_id: str, member_id: str, db: Session = Depends(get_db)
):
    _get_or_404(db, user_id, collection_id)
    member = db.get(models.CompanyCollectionMember, member_id)
    if not member or member.collection_id != collection_id:
        raise HTTPException(404, "Azienda non trovata nella collezione")
    db.delete(member)
    db.commit()


@router.post("/{collection_id}/similar", response_model=list[schemas.CompanySuggestion])
async def similar_to_collection(
    user_id: str, collection_id: str,
    payload: schemas.CollectionSimilarRequest, db: Session = Depends(get_db),
):
    """Trova aziende simili all'INTERA collezione."""
    coll = _get_or_404(db, user_id, collection_id)
    engine = CompanyDiscoveryEngine(LLMGateway(db=db))
    results = await suggest_for_collection(
        db, coll, engine, limit=payload.limit, country_code=payload.country_code
    )
    return [schemas.CompanySuggestion(**r) for r in results]


@router.get("/{collection_id}/profile")
async def get_profile(user_id: str, collection_id: str, db: Session = Depends(get_db)):
    """Il "carattere" della collezione, in una frase."""
    coll = _get_or_404(db, user_id, collection_id)
    engine = CompanyDiscoveryEngine(LLMGateway(db=db))
    return {"summary": await collection_profile(db, coll, engine)}


@router.post("/{collection_id}/apply/{session_id}")
def apply_collection(
    user_id: str, collection_id: str, session_id: str, db: Session = Depends(get_db)
):
    """Copia le aziende della collezione tra i target di una ricerca."""
    coll = _get_or_404(db, user_id, collection_id)
    added = apply_to_session(db, coll, user_id, session_id)
    return {"added": added, "total": len(coll.members)}
