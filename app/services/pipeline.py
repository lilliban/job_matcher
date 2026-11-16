"""
Pipeline di matching senza LLM: feed → prefiltro → copertura skill.
Nessun annuncio classificato viene scartato per copertura bassa: viene
solo marcato below_threshold e messo dopo gli altri.

Collega pezzi che esistono già, senza duplicarli:
  - feed_reader: download_feed, load_postings, prefilter
  - coverage:    compute_coverage, passes_threshold
  - models:      User.hard_skills (le skill del candidato)

Flusso tipico:
    db = SessionLocal()
    results = run_matching(user_id, db, "feeds_cache")
"""
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import User
from app.services.coverage import compute_coverage, passes_threshold
from app.services.feed_reader import download_feed, load_postings, prefilter
from app.services.tracking import qualifies_as_new

UNCLASSIFIED_PRIORITY = 5

# Una percentuale calcolata su una o due skill dice poco: "1 di 1" fa 100%
# ma non vale un 90% su dieci skill. A parità di priorità e di fascia
# (sopra o sotto soglia) gli annunci con almeno LOW_DATA_SKILLS skill
# misurate vengono prima; quelli con pochi dati seguono subito dopo, sempre
# visibili. La fascia pesa di più: un 100% su due skill non finisce dietro
# a uno 0% su tre. La percentuale mostrata non cambia.
LOW_DATA_SKILLS = 3


def _is_low_data(r: dict) -> bool:
    """Copertura misurata, ma su meno di LOW_DATA_SKILLS skill."""
    return r["coverage"] is not None and r["skills_measured"] < LOW_DATA_SKILLS


def load_user_skill_names(db: Session, user_id: str) -> list[str]:
    """Nomi delle hard skill del profilo, letti dalla relazione User.hard_skills
    (la stessa fonte usata da search_runner._build_user_profile)."""
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"Utente {user_id!r} non trovato")
    return [s.name for s in user.hard_skills if s.name]


def match_postings(
    postings: list[dict], user_skills: list[str], today: date | None = None
) -> list[dict]:
    """Prefiltro + copertura + ordinamento su annunci già caricati.

    La selezione favorisce il recall: meglio un annuncio in più che un
    buon match perso.
    - Priorità 1–4: l'annuncio resta sempre. `below_threshold` è vero se
      la copertura è misurata e sotto COVERAGE_THRESHOLD.
    - Priorità 5 (ruolo non classificato): resta solo se la copertura è
      misurata e maggiore di zero — senza nessun segnale dal titolo, serve
      almeno un segnale dalle skill.
    - Tesi e dottorati restano nel risultato con kind="thesis": è la pagina
      a tenerli fuori dalla lista principale.
    - `is_new`: visto per la prima volta da ieri alle 00:00 (rispetto a
      `today`, di default oggi) e con copertura almeno alla soglia, oppure
      non misurabile ma di priorità 1.
    """
    today = today or date.today()
    kept, _discarded = prefilter(postings)

    results: list[dict] = []
    for p in kept:
        text = p.get("requirements_raw") or p.get("description") or ""
        cov = compute_coverage(user_skills, text)

        pct = cov["percentage"]
        priority = p["_role_priority"]
        if priority == UNCLASSIFIED_PRIORITY and (pct is None or pct <= 0):
            continue

        results.append({
            "title": p.get("title"),
            "company_name": p.get("company_name"),
            "country_code": p.get("country_code"),
            # CH/DE/NL, "remote_eu" (remoto aperto all'Europa) o "unknown"
            "region": p["_region"],
            # "job" oppure "thesis" (tesi e dottorati: fuori dalla lista principale)
            "kind": p["_kind"],
            "source_url": p.get("source_url"),
            "priority": priority,
            "category": p["_role_category"],
            "coverage": pct,
            # passes_threshold è vero anche con copertura None: il suo
            # contrario è esattamente "misurata e sotto soglia"
            "below_threshold": not passes_threshold(cov),
            "matched_skills": cov["matched"],
            "missing_required": cov["missing_required"],
            "missing_nice": cov["missing_nice"],
            # skill dell'annuncio su cui è calcolata la copertura (richieste
            # + gradite): sotto LOW_DATA_SKILLS la percentuale è poco affidabile
            "skills_measured": len(cov["matched"]) + len(cov["missing_required"]) + len(cov["missing_nice"]),
            "first_seen_at": p.get("first_seen_at"),
            # il testo su cui è calcolata la copertura: serve al dettaglio e,
            # se l'annuncio viene salvato, a ricalcolare la stessa percentuale
            "description": text or None,
            "is_new": qualifies_as_new(p.get("first_seen_at"), pct, priority, today),
        })

    # Priorità crescente. Dentro la priorità:
    #   1. sopra soglia: prima su almeno LOW_DATA_SKILLS skill, poi pochi dati
    #   2. sotto soglia: stesso schema
    #   3. in coda gli annunci con copertura None: senza skill riconosciute
    #      nel testo non sappiamo dire nulla.
    # Dentro ogni gruppo, copertura decrescente.
    results.sort(key=lambda r: (
        r["priority"],
        r["coverage"] is None,
        r["below_threshold"],
        _is_low_data(r),
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
