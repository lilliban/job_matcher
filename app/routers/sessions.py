"""
Router: sessioni di ricerca — RF1.3, RF2, RF3, RF8

Nota architetturale: POST /run risponde 202 immediatamente e lancia il
lavoro in background. Il client fa polling su GET /status.
"""
import asyncio
import json
import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app import models, schemas
from app.database import get_db
from app.routers.users import get_user_or_404
from app.services.llm_gateway import LLMGateway
from app.services.matcher import MatchingEngine
from app.services.search_runner import register_task, request_cancel, run_search

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users/{user_id}/sessions",
    tags=["Sessioni"],
    dependencies=[Depends(verify_token)], 
)


def get_session_or_404(db: Session, user_id: str, session_id: str) -> models.SearchSession:
    session = db.get(models.SearchSession, session_id)
    if not session or session.user_id != user_id:
        raise HTTPException(404, "Sessione non trovata")
    return session


# ---------------------------------------------------------------------
# CRUD sessione
# ---------------------------------------------------------------------
@router.post("", response_model=schemas.SearchSessionOut, status_code=201)
def create_session(
    user_id: str, payload: schemas.SearchSessionCreate, db: Session = Depends(get_db)
):
    get_user_or_404(db, user_id)

    data = payload.model_dump()
    # competenze e aziende non sono colonne di SearchSession: arrivano nello
    # stesso payload perché fanno parte della definizione della ricerca, ma
    # vanno in tabelle proprie
    skills = data.pop("hard_skills", []) or []
    companies = data.pop("companies", []) or []

    session = models.SearchSession(user_id=user_id, **data)
    db.add(session)
    db.flush()

    seen_skill: set[str] = set()
    for name in skills:
        name = (name or "").strip()
        if not name or name.lower() in seen_skill:
            continue
        seen_skill.add(name.lower())
        db.add(models.SessionHardSkill(session_id=session.id, name=name))

    seen_co: set[str] = set()
    for c in companies:
        name = (c.get("name") or "").strip()
        if not name or name.lower() in seen_co:
            continue
        seen_co.add(name.lower())
        db.add(models.TargetCompany(session_id=session.id, **{**c, "name": name}))
        # stessa cortesia del percorso a una azienda per volta: ciò che
        # scegli per una ricerca resta suggerito per quelle future
        already = (
            db.query(models.UserPreferredCompany)
            .filter(
                models.UserPreferredCompany.user_id == user_id,
                models.UserPreferredCompany.name.ilike(name),
            )
            .first()
        )
        if not already:
            db.add(models.UserPreferredCompany(
                user_id=user_id, name=name, country=c.get("country"),
                size=c.get("size"), sector=c.get("sector"),
                website=c.get("website"), source=c.get("source"),
            ))

    db.commit()
    db.refresh(session)
    return session


@router.get("", response_model=list[schemas.SearchSessionOut])
def list_sessions(user_id: str, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return (
        db.query(models.SearchSession)
        .filter(models.SearchSession.user_id == user_id)
        .order_by(models.SearchSession.created_at.desc())
        .all()
    )


@router.get("/{session_id}", response_model=schemas.SearchSessionOut)
def get_session(user_id: str, session_id: str, db: Session = Depends(get_db)):
    return get_session_or_404(db, user_id, session_id)


@router.patch("/{session_id}", response_model=schemas.SearchSessionOut)
def update_session(
    user_id: str,
    session_id: str,
    payload: schemas.SearchSessionUpdate,
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user_id, session_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(session, k, v)
    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}", status_code=204)
def delete_session(user_id: str, session_id: str, db: Session = Depends(get_db)):
    session = get_session_or_404(db, user_id, session_id)
    db.delete(session)
    db.commit()


# ---------------------------------------------------------------------
# RF2.1 — skill richieste dal ruolo
# ---------------------------------------------------------------------
@router.post(
    "/{session_id}/hard-skills",
    response_model=schemas.SessionHardSkillOut,
    status_code=201,
)
def add_session_skill(
    user_id: str,
    session_id: str,
    payload: schemas.SessionHardSkillCreate,
    db: Session = Depends(get_db),
):
    session = get_session_or_404(db, user_id, session_id)
    skill = models.SessionHardSkill(session_id=session.id, **payload.model_dump())
    db.add(skill)
    db.commit()
    db.refresh(skill)
    return skill


@router.get("/{session_id}/hard-skills", response_model=list[schemas.SessionHardSkillOut])
def list_session_skills(user_id: str, session_id: str, db: Session = Depends(get_db)):
    session = get_session_or_404(db, user_id, session_id)
    return session.hard_skills


@router.delete("/{session_id}/hard-skills/{skill_id}", status_code=204)
def delete_session_skill(
    user_id: str, session_id: str, skill_id: str, db: Session = Depends(get_db)
):
    get_session_or_404(db, user_id, session_id)
    skill = db.get(models.SessionHardSkill, skill_id)
    if not skill or skill.session_id != session_id:
        raise HTTPException(404, "Skill non trovata")
    db.delete(skill)
    db.commit()


# ---------------------------------------------------------------------
# UC10 / SD2 — esecuzione ricerca in BACKGROUND
# ---------------------------------------------------------------------
@router.post("/{session_id}/run", status_code=202)
async def start_search(
    user_id: str,
    session_id: str,
    db: Session = Depends(get_db),
):
    """Avvia la ricerca e risponde SUBITO. Il client fa polling su /status."""
    session = get_session_or_404(db, user_id, session_id)

    if session.status == "running":
        raise HTTPException(409, "Una ricerca è già in corso per questa sessione")

    if not session.companies and not session.role_title:
        raise HTTPException(400, "Configura almeno il ruolo o un'azienda target")

    session.status = "running"
    session.progress_current = 0
    session.progress_total = 0
    session.progress_message = "In coda..."
    db.commit()

    # asyncio.create_task (non BackgroundTasks) perché serve l'oggetto Task
    # per poterlo cancellare da /cancel — vedi search_runner.register_task
    task = asyncio.create_task(run_search(session_id))
    register_task(session_id, task)

    return {
        "status": "running",
        "session_id": session_id,
        "message": "Ricerca avviata. Controlla lo stato su /status.",
    }


@router.post("/{session_id}/cancel", status_code=202)
def cancel_search(user_id: str, session_id: str, db: Session = Depends(get_db)):
    """Richiede l'annullamento cooperativo di una ricerca in corso.
    Non è istantaneo: il task si ferma al prossimo punto di sospensione
    (tipicamente tra un annuncio e l'altro)."""
    session = get_session_or_404(db, user_id, session_id)
    if session.status != "running":
        raise HTTPException(409, "Nessuna ricerca in corso per questa sessione")

    if not request_cancel(session_id):
        raise HTTPException(
            409, "La ricerca non è più cancellabile (probabilmente già terminata)"
        )

    session.progress_message = "Annullamento richiesto..."
    db.commit()

    return {"status": "cancelling", "session_id": session_id}


@router.get("/{session_id}/status", response_model=schemas.SessionStatusOut)
def get_status(user_id: str, session_id: str, db: Session = Depends(get_db)):
    """Polling dello stato — il frontend chiama questo ogni 2 secondi."""
    session = get_session_or_404(db, user_id, session_id)
    matches = db.query(models.Match).filter(models.Match.session_id == session_id).count()
    return schemas.SessionStatusOut(
        session_id=session.id,
        status=session.status,
        progress_current=session.progress_current or 0,
        progress_total=session.progress_total or 0,
        progress_message=session.progress_message,
        matches_found=matches,
    )


# ---------------------------------------------------------------------
# RF8.5 — log live
# ---------------------------------------------------------------------
@router.get("/{session_id}/logs", response_model=list[schemas.SearchLogOut])
def get_logs(
    user_id: str,
    session_id: str,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    get_session_or_404(db, user_id, session_id)
    return (
        db.query(models.SearchLog)
        .filter(models.SearchLog.session_id == session_id)
        .order_by(models.SearchLog.ts.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------
# Risultati
# ---------------------------------------------------------------------
@router.get("/{session_id}/listings", response_model=list[schemas.JobListingOut])
def list_listings(user_id: str, session_id: str, db: Session = Depends(get_db)):
    session = get_session_or_404(db, user_id, session_id)
    return session.listings


@router.get("/{session_id}/matches", response_model=list[schemas.MatchDetailOut])
def list_matches(
    user_id: str,
    session_id: str,
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    get_session_or_404(db, user_id, session_id)
    q = db.query(models.Match).filter(models.Match.session_id == session_id)
    if status:
        q = q.filter(models.Match.status == status)
    return q.order_by(models.Match.score.desc()).all()


# ---------------------------------------------------------------------
# RF8 — Pagina Intelligence
# ---------------------------------------------------------------------
@router.get("/{session_id}/intelligence", response_model=schemas.IntelligenceReportOut)
async def get_intelligence_report(
    user_id: str, session_id: str, db: Session = Depends(get_db)
):
    session = get_session_or_404(db, user_id, session_id)

    matches = (
        db.query(models.Match)
        .filter(models.Match.session_id == session_id)
        .order_by(models.Match.score.desc())
        .all()
    )
    listings = session.listings
    companies = session.companies

    total_matches = len(matches)
    avg_score = round(sum(m.score for m in matches) / total_matches, 3) if total_matches else 0.0
    best_score = round(max((m.score for m in matches), default=0.0), 3)

    # RF8.3 — skill mancanti più frequenti
    counter: Counter = Counter()
    for m in matches:
        try:
            for s in json.loads(m.missing_skills or "[]"):
                counter[s] += 1
        except (json.JSONDecodeError, TypeError):
            continue
    top_missing = [
        {"skill": s, "count": c, "pct": round(c / total_matches, 2) if total_matches else 0}
        for s, c in counter.most_common(8)
    ]

    # RF8.2 — perché ogni azienda non ha prodotto match
    outcomes: list[schemas.CompanyOutcome] = []
    for c in companies:
        c_listings = [l for l in listings if l.company_name.lower() == c.name.lower()]
        c_matches = [m for m in matches if m.listing and m.listing.company_name.lower() == c.name.lower()]

        if not c.exists_online:
            reason = "Azienda non trovata online — probabilmente non esiste o ha un nome diverso"
        elif not c.careers_url_verified:
            reason = "Nessuna pagina carriere raggiungibile sul sito aziendale"
        elif not c_listings:
            reason = "Pagina carriere raggiunta ma nessuna posizione aperta trovata"
        elif not c_matches:
            reason = (
                f"{len(c_listings)} posizioni aperte trovate ma nessuna compatibile "
                f"con il tuo profilo (sotto la soglia del {session.match_threshold:.0%})"
            )
        else:
            reason = f"{len(c_matches)} match trovati su {len(c_listings)} posizioni"

        outcomes.append(schemas.CompanyOutcome(
            company=c.name,
            listings_found=len(c_listings),
            matches_found=len(c_matches),
            reason=reason,
        ))

    # RF8.4 — ruoli alternativi
    alternatives: list[schemas.AlternativeRole] = []
    summary = None
    if session.status == "completed":
        try:
            llm = LLMGateway(db=db)
            matcher = MatchingEngine(llm)
            user_skills = [s.name for s in session.user.hard_skills]
            raw_alts = await matcher.suggest_alternative_roles(session.role_title, user_skills)
            alternatives = [
                schemas.AlternativeRole(
                    role=a.get("role", ""),
                    overlap=a.get("overlap"),
                    why=a.get("why"),
                )
                for a in raw_alts if isinstance(a, dict) and a.get("role")
            ]

            summary = await _build_summary(
                llm, session, len(listings), total_matches, avg_score, top_missing, outcomes
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Intelligence LLM non disponibile: %s", exc)

    sources = len({l.source_board for l in listings if l.source_board})

    return schemas.IntelligenceReportOut(
        session_id=session.id,
        role_title=session.role_title,
        status=session.status,
        sources_queried=sources,
        total_companies=len(companies),
        companies_verified=sum(1 for c in companies if c.careers_url_verified),
        total_listings=len(listings),
        total_matches=total_matches,
        avg_score=avg_score,
        best_score=best_score,
        top_missing_skills=top_missing,
        company_outcomes=outcomes,
        alternative_roles=alternatives,
        summary=summary,
    )


async def _build_summary(
    llm: LLMGateway,
    session: models.SearchSession,
    n_listings: int,
    n_matches: int,
    avg_score: float,
    top_missing: list[dict],
    outcomes: list[schemas.CompanyOutcome],
) -> str | None:
    missing_str = ", ".join(f"{m['skill']} ({m['count']}x)" for m in top_missing[:5]) or "nessuna"
    outcomes_str = "\n".join(f"- {o.company}: {o.reason}" for o in outcomes[:10]) or "nessuna azienda target"

    prompt = (
        "Scrivi un breve resoconto in italiano (massimo 6 frasi) per un candidato "
        "che ha appena eseguito una ricerca di lavoro automatica.\n\n"
        "Sii onesto ma incoraggiante. Spiega cosa è successo e cosa può fare.\n"
        "Non usare formule di cortesia inutili, vai al punto.\n\n"
        f"RUOLO CERCATO: {session.role_title}\n"
        f"ZONA: {session.location_pref or 'non specificata'}\n"
        f"ANNUNCI ANALIZZATI: {n_listings}\n"
        f"MATCH SOPRA SOGLIA ({session.match_threshold:.0%}): {n_matches}\n"
        f"SCORE MEDIO: {avg_score:.0%}\n"
        f"COMPETENZE PIÙ RICHIESTE CHE MANCANO: {missing_str}\n\n"
        f"ESITO PER AZIENDA:\n{outcomes_str}"
    )
    try:
        return await llm.complete(prompt)
    except Exception:  # noqa: BLE001
        return None
