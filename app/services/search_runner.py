"""
SearchRunner — orchestratore della ricerca (SD2).

Risolve i due problemi critici dell'implementazione precedente:
  1. Gira in BACKGROUND — la request HTTP risponde subito con 202,
     il client fa polling sullo stato. Nessun timeout.
  2. COMMIT INCREMENTALI — ogni azienda/annuncio viene salvato appena
     processato. Un crash a metà non perde il lavoro già fatto.

Ogni passo viene loggato in SearchLog: è ciò che alimenta il log live
(RF8.5) e la Pagina Intelligence (RF8).

Cancellazione cooperativa: il task viene lanciato con `asyncio.create_task`
(non `BackgroundTasks`, che non espone l'oggetto Task) e tracciato in
`_running_tasks`. `request_cancel()` chiama `Task.cancel()`, che solleva
`asyncio.CancelledError` al prossimo punto di await sospeso — tipicamente
dentro una chiamata scraper/LLM — interrompendo la ricerca senza dover
disseminare controlli di un flag in ogni ciclo.
"""
import asyncio
import json
import logging
import time  # ← AGGIUNTO: serve per misurare la durata dei commit
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import POLL_INTERVAL_SECONDS
from app.database import SessionLocal
from app.models import (
    GeneratedDocument,
    JobListing,
    Match,
    SearchLog,
    SearchSession,
    TargetCompany,
)
from app.services import company_source
from app.services.company_discovery import CompanyDiscoveryEngine
from app.services.doc_generator import DocumentGenerator
from app.services.llm_gateway import LLMGateway
from app.services.matcher import MatchingEngine
from app.services.scraper import ScraperEngine

logger = logging.getLogger(__name__)

# Soglia oltre la quale un commit è considerato "lento"
SLOW_COMMIT_THRESHOLD = 0.1  # 100ms

# session_id -> Task in corso, per la cancellazione cooperativa (RF... /cancel)
_running_tasks: dict[str, "asyncio.Task[None]"] = {}


def _commit_with_logging(db: Session, context: str = "") -> None:
    """Esegue commit con misurazione della durata.

    Se il commit dura più di SLOW_COMMIT_THRESHOLD, logga un warning.
    In caso di errore, esegue rollback e logga l'errore.
    """
    start = time.time()
    try:
        db.commit()
        duration = time.time() - start
        if duration > SLOW_COMMIT_THRESHOLD:
            logger.warning(f"⚠️ Commit lento ({duration:.3f}s) in: {context}")
    except Exception as exc:
        logger.error(f"🔴 ERRORE commit in {context}: {exc}")
        db.rollback()
        raise


def register_task(session_id: str, task: "asyncio.Task[None]") -> None:
    """Registra il task per renderlo cancellabile via request_cancel()."""
    _running_tasks[session_id] = task
    task.add_done_callback(lambda _: _running_tasks.pop(session_id, None))


def request_cancel(session_id: str) -> bool:
    """Richiede la cancellazione cooperativa. True se un task attivo è
    stato trovato e la cancellazione è stata richiesta."""
    task = _running_tasks.get(session_id)
    if task and not task.done():
        task.cancel()
        return True
    return False


def _log(db: Session, session_id: str, source: str, action: str,
         result: str, level: str = "info") -> None:
    """Scrive un evento e committa subito — il frontend lo vede al prossimo poll."""
    try:
        db.add(SearchLog(
            session_id=session_id, source=source, action=action,
            result=result, level=level,
        ))
        _commit_with_logging(db, context=f"_log: {action}")
    except Exception as exc:
        logger.debug("Log write fallito: %s", exc)
        db.rollback()


def _progress(db: Session, session: SearchSession, current: int,
              total: int, message: str) -> None:
    session.progress_current = current
    session.progress_total = total
    session.progress_message = message
    try:
        _commit_with_logging(db, context=f"_progress: {message[:50]}")
    except Exception:
        db.rollback()


def _build_user_profile(session: SearchSession) -> dict:
    u = session.user
    return {
        "name": u.name,
        "email": u.email,
        "phone": u.phone,
        "location": u.location,
        "bio": u.bio,
        "soft_skills": [s.name for s in u.soft_skills],
        "hard_skills": [
            {"name": s.name, "level": s.level, "years_exp": s.years_exp,
             "acquired_via": s.acquired_via}
            for s in u.hard_skills
        ],
        "experiences": [
            {"company": e.company, "role": e.role, "start_date": e.start_date,
             "end_date": e.end_date, "description": e.description,
             "skills_used": e.skills_used}
            for e in u.experiences
        ],
        "education": [
            {"institution": e.institution, "degree": e.degree,
             "field": e.field, "year": e.year}
            for e in u.education
        ],
        # CV e lettera "base": se ci sono, il generatore li adatta invece di
        # riscrivere da zero per ogni annuncio
        "base_documents": {
            d.doc_type: d.content for d in u.base_documents if d.content
        },
    }


async def run_search(session_id: str) -> None:
    db: Session = SessionLocal()
    try:
        session = db.get(SearchSession, session_id)
        if not session:
            logger.error("Sessione %s non trovata", session_id)
            return

        session.status = "running"
        session.progress_current = 0
        session.progress_message = "Avvio ricerca..."
        _commit_with_logging(db, context="run_search: avvio sessione")

        # 1. PRIMA crea user_profile
        user_profile = _build_user_profile(session)
        user_skill_names = [s["name"] for s in user_profile["hard_skills"]]
        required_skills = [s.name for s in session.hard_skills if s.required]

        # 2. POI crea i servizi
        llm = LLMGateway(db=db)
        scraper = ScraperEngine(llm)
        matcher = MatchingEngine(llm, user_profile=user_profile)  # ← Ora user_profile esiste
        doc_gen = DocumentGenerator(llm)
        discovery = CompanyDiscoveryEngine(llm)

        # 3. Poi il resto...
        _log(db, session_id, "system", "start",
             f"Ricerca avviata per il ruolo: {session.role_title}")

        # =============================================================
        # FASE 1 — verifica aziende target e trova le careers page
        # =============================================================
        companies = [c for c in session.companies if c.exists_online]
        total_steps = len(companies) + 1  # +1 per la fase job board
        step = 0

        for company in companies:
            step += 1
            _progress(db, session, step, total_steps,
                      f"Cerco offerte da {company.name}...")

            def _clog(action: str, result: str, level: str = "info",
                      _name=company.name) -> None:
                _log(db, session_id, _name, action, result, level=level)

            profile = company_source.get_or_create_profile(db, company)

            # RF... — riuso tra ricerche. Se questa azienda è stata
            # interrogata di recente, gli annunci sono già nel livello
            # globale: si riusano senza toccare la rete, anche se a
            # raccoglierli era stata un'ALTRA sessione. Il matching invece
            # si rifà sempre, perché è la parte personale.
            if company_source.is_fresh(profile):
                cached = company_source.cached_postings_for(db, company.name)
                if cached:
                    listings = [company_source.posting_to_item(p) for p in cached]
                    listings = company_source.filter_by_role(listings, session.role_title)
                    _clog("cache",
                          f"{len(listings)} annunci riusati dall'archivio, "
                          f"nessuna richiesta di rete")
                    outcome = "found" if listings else "no_openings"
                else:
                    listings, outcome = [], "no_openings"
                seen_in_feed = set()  # la cache non dice nulla su cosa sia sparito
            else:
                listings, outcome, seen_in_feed = await company_source.collect_for_company(
                    db, company, profile, scraper, _clog,
                    role_title=session.role_title,
                )

            company.last_searched_at = datetime.now(timezone.utc)
            company.last_result = outcome
            company.last_postings_count = len(listings)
            _commit_with_logging(db, context=f"run_search: aggiornamento company {company.name}")

            # Ciclo di vita. `seen_in_feed` sono le impronte della lettura
            # COMPLETA del feed, non degli annunci sopravvissuti al filtro
            # per ruolo: usare la lista filtrata dichiarerebbe "sparito"
            # tutto ciò che l'azienda pubblica e che non riguarda questa
            # ricerca — cercando "Data Analyst" da Datadog si chiuderebbero
            # i 400 annunci di ogni altro mestiere.
            if seen_in_feed:
                n_closed = company_source.close_missing(db, company.name, seen_in_feed)
                if n_closed:
                    _clog("lifecycle",
                          f"{n_closed} annunci non più pubblicati, marcati chiusi")

            await _process_listings(
                db, session, listings, user_skill_names, required_skills,
                user_profile, matcher, doc_gen,
            )

        # =============================================================
        # FASE 2 — job board a rotazione (RF3.1a)
        # =============================================================
        step += 1
        _progress(db, session, step, total_steps,
                  "Cerco sui portali di lavoro...")
        _log(db, session_id, "job_boards", "search",
             f"Interrogo i portali per '{session.role_title}'")

        def _log_board(board_name: str, diag: dict) -> None:
            """Un board che risponde 403 e uno che risponde 200 con una
            shell JavaScript vuota sono entrambi "0 annunci" nel log
            vecchio. Qui si distinguono, così si sa quali portali vale la
            pena tenere."""
            outcome = diag.get("outcome", "?")
            detail = f"{diag.get('listings', 0)} annunci · esito {outcome}"
            if diag.get("status") is not None:
                detail += f" · HTTP {diag['status']} · {diag.get('bytes', 0)} byte"
            if diag.get("error"):
                detail += f" · {diag['error']}"
            level = "info" if diag.get("listings") else "warning"
            _log(db, session_id, board_name, "board_result", detail, level=level)

        board_listings = await scraper.search_job_boards(
            session.role_title, session.location_pref, session.preferred_country,
            on_board_result=_log_board,
        )
        _log(db, session_id, "job_boards", "search",
             f"{len(board_listings)} annunci raccolti dai portali")

        await _process_listings(
            db, session, board_listings, user_skill_names, required_skills,
            user_profile, matcher, doc_gen,
        )

        # =============================================================
        # Chiusura
        # =============================================================
        match_count = db.query(Match).filter(Match.session_id == session_id).count()
        session.status = "completed"
        session.last_run_at = datetime.now(timezone.utc)
        session.progress_current = total_steps
        session.progress_message = f"Completato — {match_count} match trovati"
        _commit_with_logging(db, context="run_search: completamento sessione")

        _log(db, session_id, "system", "complete",
             f"Ricerca completata: {match_count} match sopra soglia")

    except asyncio.CancelledError:
        logger.info("Ricerca %s annullata dall'utente", session_id)
        try:
            session = db.get(SearchSession, session_id)
            if session:
                session.status = "cancelled"
                session.progress_message = "Ricerca annullata dall'utente"
                _commit_with_logging(db, context="run_search: cancellazione sessione")
            _log(db, session_id, "system", "cancelled",
                 "Ricerca annullata dall'utente", level="warning")
        except Exception:  # noqa: BLE001
            db.rollback()
        raise  # non ingoiare la cancellazione — è convenzione asyncio ri-sollevarla
    except Exception as exc:  # noqa: BLE001
        logger.exception("Errore nella ricerca %s", session_id)
        try:
            session = db.get(SearchSession, session_id)
            if session:
                session.status = "error"
                session.progress_message = f"Errore: {exc}"
                _commit_with_logging(db, context="run_search: errore sessione")
            _log(db, session_id, "system", "error", str(exc), level="error")
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()

async def _process_listings(
    db: Session,
    session: SearchSession,
    listings: list[dict],
    user_skills: list[str],
    required_skills: list[str],
    user_profile: dict,
    matcher: MatchingEngine,
    doc_gen: DocumentGenerator,
) -> None:
    """Per ogni annuncio: dedup → salva → match → se sopra soglia genera documenti.
    Commit dopo ogni annuncio (nessuna transazione gigante)."""
    for item in listings:
        try:
            title = (item.get("title") or "").strip()
            if not title:
                continue

            company_name = (item.get("company_name") or "N/D").strip()
            requirements = item.get("requirements_raw") or item.get("description") or ""

            # R08 — deduplicazione
            chash = ScraperEngine.content_hash(title, company_name, requirements)
            exists = (
                db.query(JobListing)
                .filter(
                    JobListing.session_id == session.id,
                    JobListing.content_hash == chash,
                )
                .first()
            )
            if exists:
                continue

            # l'annuncio entra prima nel livello globale
            posting = company_source.upsert_posting(db, item, chash)

            listing = JobListing(
                session_id=session.id,
                posting_id=posting.id,
                title=title,
                company_name=company_name,
                source_url=item.get("source_url"),
                source_board=item.get("source_board"),
                description=item.get("description"),
                requirements_raw=requirements,
                location=item.get("location"),
                contract_type=item.get("contract_type"),
                posted_date=item.get("posted_date"),
                content_hash=chash,
            )
            db.add(listing)
            _commit_with_logging(db, context=f"_process_listings: salvataggio annuncio '{title[:50]}'")
            db.refresh(listing)

            listing_dict = {
                "title": listing.title,
                "company_name": listing.company_name,
                "location": listing.location,
                "requirements_raw": listing.requirements_raw,
                "description": listing.description,
            }

            # =========================================
            # FILTRO 1: Incompatibilità (esperienza, lingue, work mode)
            # =========================================
            is_incompatible, reason = matcher.filter_incompatible(listing_dict)
            if is_incompatible:
                _log(
                    db, session.id, company_name, "filtered",
                    f"{title} — scartato: {reason}",
                    level="warning",
                )
                continue

            # =========================================
            # FILTRO 2: Seniority (stage/junior vs senior)
            # =========================================
            title_lower = title.lower()
            role_lower = session.role_title.lower()
            
            if any(word in role_lower for word in ["stage", "junior", "intern", "tirocinio"]):
                if any(word in title_lower for word in ["senior", "lead", "manager", "director", "head"]):
                    _log(
                        db, session.id, company_name, "filtered",
                        f"{title} — scartato: seniority non compatibile con stage/junior",
                        level="warning",
                    )
                    continue

            # =========================================
            # Solo se passa tutti i filtri, calcola lo score
            # =========================================
            result = await matcher.compute_score(
                user_skills, required_skills, listing_dict, user_profile
            )

            if result["score"] < session.match_threshold:
                _log(
                    db, session.id, company_name, "match_below_threshold",
                    f"{title} — score {result['score']:.0%} sotto soglia "
                    f"{session.match_threshold:.0%}",
                )
                continue

            match = Match(
                session_id=session.id,
                listing_id=listing.id,
                score=result["score"],
                keyword_score=result["keyword_score"],
                semantic_score=result["semantic_score"],
                matched_skills=result["matched_skills"],
                missing_skills=result["missing_skills"],
                gap_analysis=result["gap_analysis"],
            )
            db.add(match)
            _commit_with_logging(db, context=f"_process_listings: salvataggio match '{title[:50]}'")
            db.refresh(match)

            _log(db, session.id, company_name, "match_found",
                 f"{title} — score {result['score']:.0%}")

            # RF5 — genera i documenti per questo match
            for doc_type in ("cv", "cover_letter", "email"):
                try:
                    content = await doc_gen.generate(
                        doc_type, user_profile, listing_dict, result
                    )
                    db.add(GeneratedDocument(
                        match_id=match.id,
                        doc_type=doc_type,
                        content=content,
                        llm_model=doc_gen.llm.last_model_used,
                    ))
                    _commit_with_logging(db, context=f"_process_listings: salvataggio {doc_type}")
                except Exception as exc:
                    logger.warning("Generazione %s fallita: %s", doc_type, exc)
                    db.rollback()

        except Exception as exc:
            logger.warning("Annuncio scartato per errore: %s", exc)
            db.rollback()
            continue