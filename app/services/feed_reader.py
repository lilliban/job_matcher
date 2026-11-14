"""
Legge gli annunci raccolti nel repo lilliban/eu-job-feeds.

Flusso tipico:
    db = download_feed("feeds_cache")
    postings = load_postings(db)
    kept, discarded = prefilter(postings)
"""
import gzip
import logging
import re
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

from app.services.matcher import seniority_check

logger = logging.getLogger(__name__)

FEED_REPO = "lilliban/eu-job-feeds"
FEED_ASSET = "jobs.sqlite.gz"
CACHE_MAX_AGE_SECONDS = 6 * 3600

# Colonne lette dalla tabella postings — ordine fisso, usato anche nei test.
# Le chiavi title, company_name, location, contract_type, description e
# requirements_raw corrispondono ai nomi già usati da MatchingEngine.filter_incompatible.
POSTING_COLUMNS = [
    "title",
    "company_name",
    "location",
    "contract_type",
    "description",
    "requirements_raw",
    "seniority",
    "min_years_exp",
    "max_years_exp",
    "work_mode",
    "country_code",
    "languages",
    "source_url",
    "first_seen_at",
]

# ---------------------------------------------------------------------------
# Filtro ruoli tecnici
# ---------------------------------------------------------------------------

_TECH_KW = [
    # software / engineering
    "software", "developer", "sviluppatore", "entwickler", "programmatore", "programmeur",
    "engineer", "ingegnere", "ingenieur",
    "backend", "back-end", "frontend", "front-end", "fullstack", "full-stack",
    "mobile", "ios", "android", "flutter",
    "python", "java", "javascript", "typescript", "golang", "kotlin",
    # data
    "data", "dati", "daten",
    "analytics", "analyst", "analista", "analytiker",
    "statistician", "statistico",
    "warehouse", "pipeline", "etl",
    # BI
    "business intelligence", "tableau", "power bi", "qlik", "looker", "dbt", "bi",
    # AI / ML
    "machine learning", "deep learning", "computer vision",
    "artificial intelligence", "intelligenza artificiale",
    "nlp", "llm", "neural", "ai",
    "mlops", "dataops",
    # DevOps / cloud / infra
    "devops", "dev ops", "dev-ops", "sre",
    "cloud", "kubernetes", "k8s", "docker", "terraform",
    "infrastructure", "infrastruttura", "platform",
    # IT consulting / ERP
    "consultant", "consulente", "berater",
    "erp", "sap", "salesforce", "crm",
    # business analyst
    "business analyst",
    # demand forecasting / supply chain
    "demand forecasting", "demand planner", "forecasting",
    "supply chain", "supply-chain",
]


def _build_tech_re(keywords: list[str]) -> re.Pattern:
    sorted_kws = sorted(set(keywords), key=len, reverse=True)
    pattern = "|".join(re.escape(kw) for kw in sorted_kws)
    return re.compile(rf"\b(?:{pattern})\b", re.IGNORECASE)


_TECH_RE = _build_tech_re(_TECH_KW)


def is_tech_role(title: str) -> bool:
    """True se il titolo rientra nelle categorie tech monitorate.

    Politica: in caso di dubbio tieni l'annuncio — è meglio un falso
    positivo che perdere un match ottimo.
    """
    return bool(_TECH_RE.search(title or ""))


# ---------------------------------------------------------------------------
# Download e lettura del feed
# ---------------------------------------------------------------------------

def download_feed(cache_dir: str | Path) -> Path:
    """Scarica jobs.sqlite.gz dalla Release 'latest' di eu-job-feeds e
    lo decomprime in cache_dir.  Se il file ha meno di 6 ore non riscarica.
    Ritorna il percorso al file jobs.sqlite decompresso.

    Richiede il GitHub CLI (gh) installato e autenticato.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    db_path = cache_dir / "jobs.sqlite"

    if db_path.exists():
        age = time.time() - db_path.stat().st_mtime
        if age < CACHE_MAX_AGE_SECONDS:
            logger.info("Feed in cache (%.0f min fa), salto il download.", age / 60)
            return db_path

    if shutil.which("gh") is None:
        raise RuntimeError(
            "Il comando 'gh' (GitHub CLI) non è disponibile sul sistema. "
            "Installalo da https://cli.github.com/ e autenticati con 'gh auth login'."
        )

    gz_path = cache_dir / FEED_ASSET
    logger.info("Scarico %s da %s ...", FEED_ASSET, FEED_REPO)
    subprocess.run(
        [
            "gh", "release", "download", "latest",
            "--repo", FEED_REPO,
            "--pattern", FEED_ASSET,
            "--dir", str(cache_dir),
            "--clobber",
        ],
        check=True,
    )

    with gzip.open(gz_path, "rb") as f_in, open(db_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    gz_path.unlink(missing_ok=True)

    return db_path


def load_postings(db_path: str | Path) -> list[dict]:
    """Apre il database in sola lettura e restituisce gli annunci aperti
    (is_closed = 0) come lista di dizionari con le chiavi in POSTING_COLUMNS.
    """
    db_path = Path(db_path)
    uri = db_path.as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cols = ", ".join(POSTING_COLUMNS)
        rows = conn.execute(
            f"SELECT {cols} FROM postings WHERE is_closed = 0"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Pre-filtro combinato
# ---------------------------------------------------------------------------

def prefilter(postings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Applica is_tech_role poi seniority_check a ogni annuncio.

    Ritorna (kept, discarded).  Gli elementi di discarded hanno la chiave
    aggiuntiva '_discard_reason' con la motivazione dello scarto.
    """
    kept: list[dict] = []
    discarded: list[dict] = []

    for p in postings:
        title = p.get("title") or ""

        if not is_tech_role(title):
            discarded.append({**p, "_discard_reason": "ruolo non tecnico"})
            continue

        text = p.get("requirements_raw") or p.get("description") or ""
        is_incompatible, reason = seniority_check(title, text)
        if is_incompatible:
            discarded.append({**p, "_discard_reason": reason})
        else:
            kept.append(p)

    return kept, discarded
