"""
Candidature: dal feed e dalle ricerche a un unico elenco, senza toccare lo schema.

Un annuncio del feed non ha una ricerca alle spalle, ma `Match` richiede una
ricerca e un annuncio di ricerca (colonne NOT NULL). Invece di ricostruire la
tabella (non è un'operazione additiva in SQLite), ogni utente ha una ricerca
RISERVATA (`search_mode = "feed"`) che raccoglie gli annunci salvati dal feed.
Ne seguono gratis documenti, rigenerazione, export e cambio di stato.

Le ricerche riservate non compaiono in "Ricerche fatte": vedi FEED_MODE nei
filtri di app/routers/sessions.py.

Tutto qui sotto scrive SOLO righe nuove (o aggiorna lo `status` di un match
esistente su richiesta dell'utente). Nessuna colonna, nessuna tabella.
"""
import json
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app import models
from app.services.coverage import compute_coverage, passes_threshold
from app.services.feed_reader import role_category

# Valore riservato di SearchSession.search_mode. Il campo è già una stringa
# libera, e l'API di creazione accetta solo companies/market/both: dall'esterno
# non si può creare una ricerca "feed".
FEED_MODE = "feed"
FEED_SESSION_TITLE = "Dal feed"

# Gli stati che fanno di un match una candidatura, nell'ordine in cui la pagina
# Candidature li raggruppa. "new" (risultato di ricerca non ancora valutato) e
# "discarded" restano fuori: non sono candidature.
TRACKED_STATUSES = ("saved", "applied", "waiting", "interview", "rejected", "accepted")
STATUS_LABEL = {
    "saved": "Salvate",
    "applied": "Inviate",
    "waiting": "In attesa",
    "interview": "Colloquio",
    "rejected": "Rifiutate",
    "accepted": "Accettate",
}
# Lo stato con cui un match smette di essere una candidatura
NOT_TRACKED_STATUS = "new"

# Priorità di role_category per i titoli che non si riconoscono (vedi pipeline.py)
UNCLASSIFIED_PRIORITY = 5

# Un annuncio è "nuovo" se visto per la prima volta da ieri alle 00:00 in poi.
NEW_SINCE_DAYS = 1

MAX_TEXT_CHARS = 60_000
ALLOWED_DOC_TYPES = ("cv", "cover_letter", "email")


# ---------------------------------------------------------------------------
# Funzioni pure (niente database): sono quelle che i test provano a fondo
# ---------------------------------------------------------------------------

def parse_seen(value: str | None) -> date | None:
    """Data (locale) di un 'first_seen_at' del feed; None se illeggibile."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.date()


def is_new_since(first_seen_at: str | None, today: date) -> bool:
    """Primo avvistamento da ieri alle 00:00 in poi (e non nel futuro)."""
    seen = parse_seen(first_seen_at)
    if seen is None:
        return False
    return today - timedelta(days=NEW_SINCE_DAYS) <= seen <= today


def qualifies_as_new(
    first_seen_at: str | None, coverage: float | None, priority: int, today: date
) -> bool:
    """Un annuncio entra tra i "Nuovi da ieri" se è nuovo E: copertura almeno
    pari alla soglia del feed, oppure copertura non misurabile ma priorità 1
    (senza skill riconosciute nel testo, conta solo quanto il ruolo è in linea)."""
    if not is_new_since(first_seen_at, today):
        return False
    if coverage is None:
        return priority == 1
    return passes_threshold({"percentage": coverage})


def is_off_profile(title: str | None, coverage: float | None) -> bool:
    """"Poco legato al tuo profilo". Stessa logica del feed, che scarta questi
    annunci: il titolo non è un ruolo tech (role_category dà None), oppure il
    ruolo non è classificabile (priorità 5) e dalle skill non arriva nessun
    segnale; oppure la copertura è misurata e a zero."""
    rc = role_category(title or "")
    if rc is None:
        return True
    if coverage is not None and coverage <= 0:
        return True
    return rc[1] == UNCLASSIFIED_PRIORITY and coverage is None


def scores_are_uniform(scores: list[float | None]) -> bool:
    """True se il punteggio della ricerca vecchia (la "Pertinenza") è identico
    per tutti gli annunci: in quel caso non aiuta a scegliere."""
    values = [round(float(s or 0.0), 6) for s in scores]
    return len(values) > 1 and len(set(values)) == 1


def match_sort_key(item: dict) -> tuple:
    """Ordine di "Ricerche fatte": prima i legati al profilo, poi gli altri;
    dentro ogni gruppo copertura decrescente, copertura non misurabile in coda."""
    cov = item.get("coverage")
    return (bool(item.get("off_profile")), cov is None, -(cov or 0.0))


def group_by_status(rows: list[dict]) -> list[dict]:
    """Raggruppa le candidature per stato, SEMPRE nell'ordine fisso di
    TRACKED_STATUSES e con tutti i gruppi presenti (anche vuoti). Le righe di
    stato non tracciato vengono ignorate. Dentro il gruppo, le più recenti prima."""
    groups = []
    for status in TRACKED_STATUSES:
        items = [r for r in rows if r["status"] == status]
        items.sort(key=lambda r: r.get("created_at") or datetime.min, reverse=True)
        groups.append({
            "status": status,
            "label": STATUS_LABEL[status],
            "count": len(items),
            "items": items,
        })
    return groups


def listing_text(listing: models.JobListing) -> str:
    """Il testo su cui è calcolata la copertura (stesso criterio del feed)."""
    return listing.requirements_raw or listing.description or ""


def insight_for(user_skills: list[str], listing: models.JobListing) -> dict:
    """Copertura "N di M skill" di un annuncio salvato, calcolata al volo con
    la stessa funzione del feed: la metrica è una sola, e non si scrive nulla."""
    cov = compute_coverage(user_skills, listing_text(listing))
    pct = cov["percentage"]
    posting = listing.posting
    return {
        "coverage": pct,
        "skills_measured": (
            len(cov["matched"]) + len(cov["missing_required"]) + len(cov["missing_nice"])
        ),
        "have": cov["matched"],
        "missing_required": cov["missing_required"],
        "missing_nice": cov["missing_nice"],
        "below_threshold": not passes_threshold(cov),
        "country_code": posting.country_code if posting else None,
        "off_profile": is_off_profile(listing.title, pct),
        "origin": origin_of(listing),
    }


def origin_of(listing: models.JobListing) -> str:
    session = listing.session
    return "feed" if session is not None and session.search_mode == FEED_MODE else "search"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_or_create_feed_session(db: Session, user_id: str) -> models.SearchSession:
    session = (
        db.query(models.SearchSession)
        .filter(
            models.SearchSession.user_id == user_id,
            models.SearchSession.search_mode == FEED_MODE,
        )
        .first()
    )
    if session is None:
        session = models.SearchSession(
            user_id=user_id,
            role_title=FEED_SESSION_TITLE,
            search_mode=FEED_MODE,
            status="completed",
        )
        db.add(session)
        db.flush()
    return session


def find_existing_match(
    db: Session, user_id: str, source_url: str | None, content_hash: str
) -> models.Match | None:
    """Lo stesso annuncio, già presente tra i match dell'utente: salvato dal
    feed o trovato da una ricerca. Prima per indirizzo, poi per hash."""
    base = (
        db.query(models.Match)
        .join(models.JobListing, models.JobListing.id == models.Match.listing_id)
        .join(models.SearchSession, models.SearchSession.id == models.Match.session_id)
        .filter(models.SearchSession.user_id == user_id)
    )
    candidates: list[models.Match] = []
    if source_url:
        candidates = base.filter(models.JobListing.source_url == source_url).all()
    if not candidates:
        candidates = base.filter(models.JobListing.content_hash == content_hash).all()
    if not candidates:
        return None
    # se ce n'è più di uno preferisco una candidatura già tracciata
    candidates.sort(key=lambda m: (m.status not in TRACKED_STATUSES, m.created_at or datetime.min))
    return candidates[0]


def save_from_feed(
    db: Session,
    user: models.User,
    *,
    title: str,
    company_name: str | None,
    source_url: str | None,
    country_code: str | None,
    region: str,
    text: str | None,
    first_seen_at: str | None,
    status: str | None,
) -> models.Match:
    """Salva un annuncio del feed come candidatura (idempotente).

    `status` None = "Salva": diventa `saved` se non lo era già, ma non
    declassa una candidatura più avanti (per esempio `applied`).
    La copertura la ricalcola il server dal testo: il numero del browser non conta."""
    # import locale: scraper porta con sé httpx e bs4, che servono solo qui
    from app.services.scraper import ScraperEngine

    text = (text or "")[:MAX_TEXT_CHARS]
    company = (company_name or "").strip() or "Azienda non indicata"
    chash = ScraperEngine.content_hash(title or "", company, text)

    match = find_existing_match(db, user.id, source_url, chash)
    if match is not None:
        if status is not None:
            match.status = status
        elif match.status not in TRACKED_STATUSES:
            match.status = "saved"
        db.commit()
        db.refresh(match)
        return match

    skills = [s.name for s in user.hard_skills if s.name]
    cov = compute_coverage(skills, text)
    pct = cov["percentage"]

    posting = (
        db.query(models.JobPosting).filter(models.JobPosting.content_hash == chash).first()
    )
    if posting is None:
        posting = models.JobPosting(
            content_hash=chash,
            title=title,
            company_name=company,
            source_url=source_url,
            source_board="feed",
            source_kind="feed",
            requirements_raw=text or None,
            location="Remoto in Europa" if region == "remote_eu" else None,
            country_code=(country_code or None),
        )
        db.add(posting)
        db.flush()

    session = get_or_create_feed_session(db, user.id)
    listing = models.JobListing(
        session_id=session.id,
        posting_id=posting.id,
        title=title,
        company_name=company,
        source_url=source_url,
        source_board="feed",
        requirements_raw=text or None,
        location=posting.location,
        posted_date=first_seen_at,
        content_hash=chash,
    )
    db.add(listing)
    db.flush()

    match = models.Match(
        session_id=session.id,
        listing_id=listing.id,
        score=pct or 0.0,
        keyword_score=pct or 0.0,
        semantic_score=0.0,
        matched_skills=json.dumps(cov["matched"]),
        missing_skills=json.dumps(cov["missing_required"]),
        status=status or "saved",
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


def save_documents(
    db: Session, match: models.Match, documents: dict[str, str], llm_model: str | None
) -> list[models.GeneratedDocument]:
    """Salva i documenti generati sulla candidatura. Un documento per tipo:
    se c'è già, il testo viene sostituito (come fa la rigenerazione)."""
    saved = []
    for doc_type, content in documents.items():
        if doc_type not in ALLOWED_DOC_TYPES or not content:
            continue
        existing = next((d for d in match.documents if d.doc_type == doc_type), None)
        if existing is not None:
            existing.content = content
            existing.llm_model = llm_model
            saved.append(existing)
        else:
            doc = models.GeneratedDocument(
                match_id=match.id, doc_type=doc_type, content=content, llm_model=llm_model
            )
            db.add(doc)
            saved.append(doc)
    # una candidatura con documenti pronti è almeno "salvata"
    if saved and match.status not in TRACKED_STATUSES:
        match.status = "saved"
    db.commit()
    return saved
