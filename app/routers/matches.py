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
from app.services import tracking
from app.services.pipeline import run_matching

logger = logging.getLogger(__name__)



router = APIRouter(prefix="/api/matches", tags=["Match"],
    dependencies=[Depends(verify_token)])

# Il campo Match.status è una stringa libera nel database (nessun vincolo):
# l'elenco dei valori ammessi vive solo qui.
VALID_STATUSES = {
    "new", "saved", "applied", "waiting", "interview", "accepted", "rejected", "discarded",
}

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
    Ordinati per priorità; dentro la priorità prima chi supera la soglia,
    poi chi è sotto, in coda le coperture non misurabili. In ogni fascia
    prima le coperture su almeno 3 skill, subito dopo quelle con pochi dati.
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


def user_skill_names(user: models.User | None) -> list[str]:
    return [s.name for s in (user.hard_skills if user else []) if s.name]


def with_insight(
    match: models.Match, skills: list[str], uniform: bool, out_cls
):
    """Un match con la sua copertura, calcolata al volo (non è nel database)."""
    out = out_cls.model_validate(match)
    if match.listing is None:
        return out
    return out.model_copy(update={
        **tracking.insight_for(skills, match.listing),
        "pertinenza_uniform": uniform,
    })


def session_uniform_flags(db: Session, session_ids: set[str]) -> dict[str, bool]:
    """Per ogni ricerca: il punteggio (Pertinenza) è uguale per tutti i suoi match?"""
    flags: dict[str, bool] = {}
    for sid in session_ids:
        scores = [r[0] for r in db.query(models.Match.score).filter(models.Match.session_id == sid)]
        flags[sid] = tracking.scores_are_uniform(scores)
    return flags


# Dichiarati PRIMA di /{match_id}: "tracked" non deve essere letto come un id.
@router.get("/tracked", response_model=list[schemas.TrackedGroupOut])
def tracked_matches(
    user_id: str = Query(..., description="Utente di cui leggere le candidature"),
    db: Session = Depends(get_db),
):
    """Le candidature di tutte le ricerche e del feed, raggruppate per stato:
    Salvate, Inviate, In attesa, Colloquio, Rifiutate, Accettate (sempre tutte,
    anche vuote). I match "new" e "scartati" non sono candidature."""
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")

    matches = (
        db.query(models.Match)
        .join(models.SearchSession, models.SearchSession.id == models.Match.session_id)
        .filter(
            models.SearchSession.user_id == user_id,
            models.Match.status.in_(tracking.TRACKED_STATUSES),
        )
        .all()
    )
    skills = user_skill_names(user)
    uniform = session_uniform_flags(db, {m.session_id for m in matches})
    rows = [
        with_insight(m, skills, uniform.get(m.session_id, False), schemas.TrackedMatchOut)
        for m in matches
    ]
    # group_by_status lavora su dizionari: riuso la stessa logica nei test
    grouped = tracking.group_by_status(
        [{"status": r.status, "created_at": r.created_at, "row": r} for r in rows]
    )
    return [
        schemas.TrackedGroupOut(
            status=g["status"], label=g["label"], count=g["count"],
            items=[i["row"] for i in g["items"]],
        )
        for g in grouped
    ]


@router.post("/from-feed", response_model=schemas.TrackedMatchOut)
def save_feed_match(payload: schemas.FeedSaveIn, db: Session = Depends(get_db)):
    """Salva un annuncio del feed come candidatura (idempotente: lo stesso
    annuncio, anche se trovato da una ricerca, resta una candidatura sola)."""
    user = db.get(models.User, payload.user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")
    if payload.status is not None and payload.status not in tracking.TRACKED_STATUSES:
        raise HTTPException(
            400, f"Stato non valido. Ammessi: {', '.join(tracking.TRACKED_STATUSES)}"
        )
    match = tracking.save_from_feed(
        db, user,
        title=payload.title.strip(),
        company_name=payload.company_name,
        source_url=(payload.source_url or "").strip() or None,
        country_code=payload.country_code,
        region=payload.region,
        text=payload.description,
        first_seen_at=payload.first_seen_at,
        status=payload.status,
    )
    uniform = session_uniform_flags(db, {match.session_id})
    return with_insight(
        match, user_skill_names(user), uniform.get(match.session_id, False), schemas.TrackedMatchOut
    )


@router.get("/{match_id}", response_model=schemas.MatchDetailOut)
def get_match(match_id: str, db: Session = Depends(get_db)):
    match = get_match_or_404(db, match_id)
    user = match.session.user if match.session else None
    uniform = session_uniform_flags(db, {match.session_id})
    return with_insight(
        match, user_skill_names(user), uniform.get(match.session_id, False), schemas.MatchDetailOut
    )


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
