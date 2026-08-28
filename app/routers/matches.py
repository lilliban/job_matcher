"""
Router: match e tracking candidature — RF4.4, RF6
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import verify_token
from app import models, schemas
from app.database import get_db

logger = logging.getLogger(__name__)



router = APIRouter(prefix="/api/matches", tags=["Match"],
    dependencies=[Depends(verify_token)])

VALID_STATUSES = {"new", "saved", "applied", "interview", "rejected", "discarded"}


def get_match_or_404(db: Session, match_id: str) -> models.Match:
    match = db.get(models.Match, match_id)
    if not match:
        raise HTTPException(404, "Match non trovato")
    return match


@router.get("/{match_id}", response_model=schemas.MatchDetailOut)
def get_match(match_id: str, db: Session = Depends(get_db)):
    return get_match_or_404(db, match_id)


@router.patch("/{match_id}/status", response_model=schemas.MatchOut)
def update_status(
    match_id: str, payload: schemas.MatchStatusUpdate, db: Session = Depends(get_db)
):
    """RF6.1 — traccia lo stato della candidatura."""
    if payload.status not in VALID_STATUSES:
        raise HTTPException(
            400, f"Stato non valido. Ammessi: {', '.join(sorted(VALID_STATUSES))}"
        )
    match = get_match_or_404(db, match_id)
    match.status = payload.status
    db.commit()
    db.refresh(match)
    return match


@router.get("/{match_id}/documents", response_model=list[schemas.GeneratedDocumentOut])
def list_documents(match_id: str, db: Session = Depends(get_db)):
    match = get_match_or_404(db, match_id)
    return match.documents


@router.delete("/{match_id}", status_code=204)
def discard_match(match_id: str, db: Session = Depends(get_db)):
    """RF4.4 — l'utente scarta manualmente un match."""
    match = get_match_or_404(db, match_id)
    db.delete(match)
    db.commit()
