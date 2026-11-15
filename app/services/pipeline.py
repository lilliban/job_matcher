"""
Pipeline di matching senza LLM: feed → prefiltro → copertura skill.

Collega pezzi che esistono già, senza duplicarli:
  - feed_reader: download_feed, load_postings, prefilter
  - coverage:    compute_coverage, passes_threshold
  - models:      User.hard_skills (le skill del candidato)

Flusso tipico:
    db = SessionLocal()
    results = run_matching(user_id, db, "feeds_cache")
"""
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import User
from app.services.coverage import compute_coverage, passes_threshold
from app.services.feed_reader import download_feed, load_postings, prefilter

UNCLASSIFIED_PRIORITY = 5


def load_user_skill_names(db: Session, user_id: str) -> list[str]:
    """Nomi delle hard skill del profilo, letti dalla relazione User.hard_skills
    (la stessa fonte usata da search_runner._build_user_profile)."""
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"Utente {user_id!r} non trovato")
    return [s.name for s in user.hard_skills if s.name]


def match_postings(postings: list[dict], user_skills: list[str]) -> list[dict]:
    """Prefiltro + copertura + soglia + ordinamento su annunci già caricati.

    Un annuncio resta se passes_threshold è vero. Quelli di priorità 5
    (ruolo non classificato) devono in più avere una copertura misurata e
    maggiore di zero: senza nessun segnale dal titolo, serve almeno un
    segnale dalle skill.
    """
    kept, _discarded = prefilter(postings)

    results: list[dict] = []
    for p in kept:
        text = p.get("requirements_raw") or p.get("description") or ""
        cov = compute_coverage(user_skills, text)
        if not passes_threshold(cov):
            continue

        pct = cov["percentage"]
        priority = p["_role_priority"]
        if priority == UNCLASSIFIED_PRIORITY and (pct is None or pct <= 0):
            continue

        results.append({
            "title": p.get("title"),
            "company_name": p.get("company_name"),
            "country_code": p.get("country_code"),
            "source_url": p.get("source_url"),
            "priority": priority,
            "category": p["_role_category"],
            "coverage": pct,
            "matched_skills": cov["matched"],
            "missing_required": cov["missing_required"],
            "missing_nice": cov["missing_nice"],
            "first_seen_at": p.get("first_seen_at"),
        })

    # Priorità crescente, poi copertura decrescente; la copertura None
    # (nessuna skill riconosciuta nel testo) va in fondo alla sua priorità.
    results.sort(key=lambda r: (
        r["priority"],
        r["coverage"] is None,
        -(r["coverage"] or 0.0),
    ))
    return results


def run_matching(user_id: str, db: Session, cache_dir: str | Path) -> list[dict]:
    """Scarica il feed e ritorna gli annunci compatibili con il profilo
    dell'utente, ordinati per priorità e copertura. Non usa l'LLM."""
    feed_path = download_feed(cache_dir)
    postings = load_postings(feed_path)
    user_skills = load_user_skill_names(db, user_id)
    return match_postings(postings, user_skills)
