"""
Router: match e tracking candidature — RF4.4, RF6
"""
import logging
import sqlite3
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.config import BASE_DIR
from app.core.security import verify_token
from app import models, schemas
from app.database import get_db
from app.services.pipeline import run_matching

logger = logging.getLogger(__name__)



router = APIRouter(prefix="/api/matches", tags=["Match"],
    dependencies=[Depends(verify_token)])

VALID_STATUSES = {"new", "saved", "applied", "interview", "rejected", "discarded"}

# Stessa cartella usata dagli script: download_feed riusa il file se ha
# meno di 6 ore, quindi le richieste ravvicinate non toccano la rete.
FEED_CACHE_DIR = BASE_DIR / "feeds_cache"

FEED_UNAVAILABLE = (
    "Il feed degli annunci non è disponibile in questo momento. "
    "Riprova tra qualche minuto."
)


# Dichiarato PRIMA di /{match_id}: altrimenti "feed" verrebbe letto come
# l'id di un match.
@router.get("/feed", response_model=list[schemas.FeedMatchOut])
def feed_matches(
    user_id: str = Query(..., description="Utente di cui leggere le hard skill"),
    db: Session = Depends(get_db),
):
    """Annunci del feed compatibili con le skill del profilo, senza LLM.
    Ordinati per priorità; dentro la priorità prima le coperture misurate
    (sopra soglia, poi sotto soglia), in coda quelle non misurabili.
    Tesi e dottorati sono inclusi con kind="thesis"."""
    if not db.get(models.User, user_id):
        raise HTTPException(404, "Utente non trovato")
    try:
        return run_matching(user_id, db, FEED_CACHE_DIR)
    except (RuntimeError, subprocess.CalledProcessError, sqlite3.Error, OSError, EOFError) as exc:
        # gh mancante o non autenticato, download fallito, file corrotto
        logger.error("Feed non disponibile: %s", exc)
        raise HTTPException(503, FEED_UNAVAILABLE) from exc


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
