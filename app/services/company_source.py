"""
Da dove arrivano gli annunci di un'azienda, e in che ordine provarci.

Tre percorsi, dal più economico al più costoso:

  1. Cache        — l'azienda è stata interrogata da poco (LISTING_TTL_HOURS):
                    non si tocca la rete. Vale tra sessioni e tra ricerche
                    diverse, perché il registro è globale.
  2. Connettore   — l'azienda ha un ATS pubblico noto: una richiesta JSON,
     ATS          nessuna chiamata LLM, campi già strutturati.
  3. Scraping     — nessun ATS: si ricade sul percorso storico (careers page
     HTML         + parsing LLM, ADR-008), che resta invariato.

Il registro (CompanyProfile) è ciò che rende stabile questa scelta nel
tempo: careers_url e provider ATS si scoprono una volta e valgono per tutte
le ricerche successive, di qualunque sessione.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import (
    ATS_MAX_LISTINGS_PER_COMPANY,
    ATS_REPROBE_DAYS,
    LISTING_TTL_HOURS,
)
from app.models import CompanyProfile, JobPosting, TargetCompany
from app.services import normalize
from app.services.ats import registry
from app.services.scraper import ScraperEngine

logger = logging.getLogger(__name__)

# parole troppo comuni nei titoli per dire qualcosa sul ruolo
_STOPWORDS = {
    "senior", "junior", "lead", "principal", "staff", "head", "of", "and",
    "the", "di", "del", "della", "e", "per", "a", "in", "il", "la",
    "manager", "specialist", "expert", "associate", "intern", "internship",
    "stage", "tirocinio", "full", "part", "time", "remote", "hybrid",
}


def _title_tokens(text: str) -> set[str]:
    return {
        t for t in re.split(r"[^a-zA-Z0-9]+", (text or "").lower())
        if len(t) > 1 and t not in _STOPWORDS
    }


def stamp_company(listings: list[dict], company_name: str) -> list[dict]:
    """Scrive il nome dell'azienda su ogni annuncio.

    Serve perché un connettore ATS conosce solo lo *slug* con cui l'azienda
    è registrata sul provider (`datadog`), non il nome con cui l'utente la
    cerca ("Datadog"). Senza questo passaggio gli annunci finivano salvati
    come "N/D" e `cached_postings_for` non li ritrovava più: la cache si
    riempiva ma nessuno riusciva a leggerla."""
    for item in listings:
        if not item.get("company_name"):
            item["company_name"] = company_name
    return listings


def filter_by_role(listings: list[dict], role_title: str) -> list[dict]:
    """Tiene solo gli annunci il cui titolo ha attinenza col ruolo cercato.

    Serve perché un feed ATS è di natura diversa da una ricerca su un
    portale: l'URL di un portale contiene già il ruolo, quindi torna una
    lista pre-filtrata; il feed di un'azienda invece è il suo catalogo
    completo — Datadog ne espone 429. Senza questo filtro una singola
    azienda inonderebbe la pipeline di annunci mai richiesti, e il costo si
    pagherebbe a valle in punteggi e righe di database.

    Volutamente permissivo: basta una parola significativa in comune. Il
    giudizio fine tocca al matcher, che è la cosa che sa farlo — qui si
    scarta solo ciò che è palesemente un altro mestiere."""
    wanted = _title_tokens(role_title)
    if not wanted:
        return listings[:ATS_MAX_LISTINGS_PER_COMPANY]

    kept = [l for l in listings if _title_tokens(l.get("title", "")) & wanted]
    return kept[:ATS_MAX_LISTINGS_PER_COMPANY]


def get_or_create_profile(db: Session, company: TargetCompany) -> CompanyProfile:
    """Trova (o crea) il profilo globale di questa azienda e vi collega la
    TargetCompany di sessione."""
    key = registry.name_key(company.name)
    profile = (
        db.query(CompanyProfile).filter(CompanyProfile.name_key == key).first()
    )
    if profile is None:
        profile = CompanyProfile(
            name_key=key,
            display_name=company.name,
            website=company.website,
            country_code=company.country,
        )
        db.add(profile)
        db.flush()

    # il profilo si arricchisce con ciò che la sessione sa in più
    if not profile.website and company.website:
        profile.website = company.website
    # la careers page trovata in una sessione precedente vale anche qui
    if not company.careers_url and profile.careers_url:
        company.careers_url = profile.careers_url
        company.careers_url_verified = profile.careers_url_verified

    company.company_profile_id = profile.id
    db.commit()
    return profile


def _should_probe_ats(profile: CompanyProfile) -> bool:
    """Se vale la pena (ri)cercare l'ATS di questa azienda.

    Mai sondata → sì. Sondata con esito negativo → sì, ma solo dopo
    ATS_REPROBE_DAYS: riprovare a ogni ricerca sprecherebbe una ventina di
    richieste per azienda, non riprovare mai renderebbe il fallimento
    eterno."""
    if profile.ats_provider and profile.ats_slug:
        return False
    if not profile.ats_probed_at:
        return True
    if not profile.ats_probe_failed:
        return True
    probed = profile.ats_probed_at
    if probed.tzinfo is None:
        probed = probed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - probed > timedelta(days=ATS_REPROBE_DAYS)


def _fresh(profile: CompanyProfile) -> bool:
    if not profile.last_fetched_at or LISTING_TTL_HOURS <= 0:
        return False
    last = profile.last_fetched_at
    if last.tzinfo is None:  # SQLite restituisce datetime naive
        last = last.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last < timedelta(hours=LISTING_TTL_HOURS)


async def collect_for_company(
    db: Session,
    company: TargetCompany,
    profile: CompanyProfile,
    scraper: ScraperEngine,
    log,
    role_title: str = "",
) -> tuple[list[dict], str, set[str]]:
    """Ritorna (annunci, esito). L'esito finisce su
    TargetCompany.last_result ed è ciò che la UI mostra accanto all'azienda.

    `log(action, result, level)` scrive nel log della sessione."""

    # --- 1. ATS già noto: percorso veloce ---------------------------------
    if profile.ats_provider and profile.ats_slug:
        listings = await registry.fetch_known(profile.ats_provider, profile.ats_slug)
        if listings is not None:
            _stamp(db, profile, ok=True)
            full = stamp_company(listings, company.name)
            kept = filter_by_role(full, role_title)
            log("ats_fetch",
                f"{len(kept)} annunci pertinenti su {len(listings)} pubblicati "
                f"da {profile.ats_provider} (nessuna chiamata LLM)")
            return kept, ("found" if kept else "no_openings"), feed_hashes(full, company.name)
        # l'ATS non risponde piu': si riprova a scoprirlo la prossima volta
        log("ats_fetch",
            f"{profile.ats_provider} non risponde più, torno allo scraping",
            "warning")
        profile.ats_provider = None
        profile.ats_slug = None
        profile.ats_probed_at = None
        db.commit()

    # --- 2. Mai sondato (o sondato troppo tempo fa) -----------------------
    # Il fallimento non è definitivo: un'azienda può adottare Greenhouse il
    # mese dopo che l'abbiamo cercata. Senza una scadenza resterebbe per
    # sempre sul percorso costoso — scaricare la pagina e farla leggere
    # all'LLM — anche molto dopo che il percorso gratuito è diventato
    # disponibile.
    if _should_probe_ats(profile):
        found = await registry.discover(profile.display_name, profile.website)
        profile.ats_probed_at = datetime.now(timezone.utc)
        if found:
            profile.ats_provider = found["provider"]
            profile.ats_slug = found["slug"]
            profile.ats_probe_failed = False
            _stamp(db, profile, ok=True)
            full = stamp_company(found["listings"], company.name)
            kept = filter_by_role(full, role_title)
            log("ats_discovery",
                f"trovato su {found['provider']}: {len(kept)} annunci pertinenti "
                f"su {len(found['listings'])} pubblicati, senza scraping")
            return kept, ("found" if kept else "no_openings"), feed_hashes(full, company.name)
        profile.ats_probe_failed = True
        db.commit()
        log("ats_discovery", "nessun ATS pubblico, uso la pagina carriere")

    # --- 3. Fallback: careers page + parsing LLM (percorso storico) -------
    if not company.careers_url:
        log("find_careers", "Cerco la pagina carriere...")
        url = await scraper.find_careers_url(company.name, company.website)
        if url:
            company.careers_url = url
            company.careers_url_verified = True
            profile.careers_url = url
            profile.careers_url_verified = True
            db.commit()
            log("find_careers", f"Pagina carriere trovata: {url}")
        else:
            _stamp(db, profile, ok=False)
            log("find_careers", "Nessuna pagina carriere raggiungibile", "warning")
            return [], "unreachable", set()

    listings = stamp_company(
        await scraper.scrape_company_careers(company.name, company.careers_url),
        company.name,
    )
    _stamp(db, profile, ok=True)
    log("scrape", f"{len(listings)} annunci trovati")
    return listings, ("found" if listings else "no_openings"), feed_hashes(listings, company.name)


def upsert_posting(db: Session, item: dict, content_hash: str) -> "JobPosting":
    """Inserisce l'annuncio nel livello globale, o aggiorna quello esistente.

    È il punto in cui un annuncio smette di appartenere a una ricerca e
    diventa un fatto del sistema: la seconda ricerca che lo incontra lo
    ritrova invece di riscaricarlo."""
    posting = (
        db.query(JobPosting).filter(JobPosting.content_hash == content_hash).first()
    )
    item = normalize.enrich(item)
    now = datetime.now(timezone.utc)

    if posting is None:
        posting = JobPosting(
            content_hash=content_hash,
            title=(item.get("title") or "").strip(),
            company_name=(item.get("company_name") or "N/D").strip(),
            source_url=item.get("source_url"),
            source_board=item.get("source_board"),
            source_kind=item.get("source_kind") or "board",
            description=item.get("description"),
            requirements_raw=item.get("requirements_raw"),
            location=item.get("location"),
            contract_type=item.get("contract_type"),
            posted_date=item.get("posted_date"),
            seniority=item.get("seniority"),
            department=item.get("department"),
            first_seen_at=now,
        )
        db.add(posting)

    # i campi normalizzati si riscrivono a ogni avvistamento: il testo
    # dell'annuncio può cambiare, e le regole di estrazione pure
    for field in ("contract_type_norm", "work_mode", "min_years_exp",
                  "max_years_exp", "languages", "city", "country_code",
                  "salary_min", "salary_max", "salary_currency"):
        setattr(posting, field, item.get(field))

    posting.last_seen_at = now
    posting.consecutive_misses = 0
    posting.is_closed = False
    db.flush()
    return posting


def cached_postings_for(db: Session, company_name: str) -> list["JobPosting"]:
    """Annunci già noti di un'azienda, non chiusi. È ciò che permette a una
    ricerca NUOVA di partire senza toccare la rete."""
    return (
        db.query(JobPosting)
        .filter(
            JobPosting.company_name.ilike(company_name),
            JobPosting.is_closed.is_(False),
        )
        .all()
    )


def posting_to_item(p: "JobPosting") -> dict:
    """Da riga in archivio al dizionario che il resto della pipeline si
    aspetta — così un annuncio riusato dalla cache e uno appena scaricato
    percorrono esattamente lo stesso cammino."""
    return {
        "title": p.title,
        "company_name": p.company_name,
        "source_url": p.source_url,
        "source_board": p.source_board,
        "source_kind": p.source_kind,
        "description": p.description,
        "requirements_raw": p.requirements_raw,
        "location": p.location,
        "contract_type": p.contract_type,
        "posted_date": p.posted_date,
        "work_mode": p.work_mode,
        "seniority": p.seniority,
        "department": p.department,
    }


def feed_hashes(listings: list[dict], company_name: str) -> set[str]:
    """Impronte di TUTTI gli annunci di una lettura del feed.

    Va calcolata sulla lista COMPLETA, prima di `filter_by_role`: è la
    fotografia di cosa l'azienda pubblica, non di cosa interessa a questa
    ricerca."""
    from app.services.scraper import ScraperEngine

    return {
        ScraperEngine.content_hash(
            (i.get("title") or "").strip(),
            (i.get("company_name") or company_name).strip(),
            i.get("requirements_raw") or i.get("description") or "",
        )
        for i in listings if i.get("title")
    }


def close_missing(db: Session, company_name: str, seen_hashes: set[str]) -> int:
    """Ciclo di vita: un annuncio assente da DUE letture complete
    consecutive del feed della sua azienda viene considerato chiuso.

    Due e non una perché una lettura può fallire o tornare parziale per
    ragioni che non hanno niente a che vedere con la posizione. Ci si basa
    sulla presenza nel feed e non sulle date di scadenza dichiarate, che
    sono spesso assenti o sbagliate.

    ATTENZIONE a cosa si passa in `seen_hashes`: deve essere la lettura
    COMPLETA del feed. Passare la lista già filtrata per ruolo significa
    dichiarare "sparito" tutto ciò che l'azienda pubblica e che non
    riguarda questa ricerca — cercando "Data Analyst" da Datadog si
    chiuderebbero i 400 annunci di ogni altro mestiere. Usa `feed_hashes`
    sulla lista non filtrata."""
    closed = 0
    for p in cached_postings_for(db, company_name):
        if p.content_hash in seen_hashes:
            continue
        p.consecutive_misses = (p.consecutive_misses or 0) + 1
        if p.consecutive_misses >= 2:
            p.is_closed = True
            closed += 1
    db.commit()
    return closed


def _stamp(db: Session, profile: CompanyProfile, ok: bool) -> None:
    profile.last_fetched_at = datetime.now(timezone.utc)
    profile.consecutive_fetch_failures = (
        0 if ok else (profile.consecutive_fetch_failures or 0) + 1
    )
    db.commit()


def is_fresh(profile: CompanyProfile) -> bool:
    """Esposta perché search_runner decida se saltare del tutto l'azienda."""
    return _fresh(profile)
