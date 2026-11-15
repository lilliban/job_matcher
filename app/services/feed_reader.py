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

ALLOWED_COUNTRIES = ["CH", "DE", "NL"]
EUROPE_COUNTRIES = [
    "CH", "DE", "NL", "IT", "AT", "FR", "BE", "LU", "ES", "PT",
    "IE", "GB", "PL", "SE", "DK", "NO", "FI",
]

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
# Classificazione ruoli tech a livelli (priorità 1–5)
# ---------------------------------------------------------------------------

# Lista nera: titoli con queste parole sono scartati come "non tecnici",
# a meno che contengano anche "software", "data", "ai" o "it"
_BLACKLIST_RE = re.compile(
    r"\bsales\b"
    r"|\bvertrieb\b"
    r"|\bverkauf\b"
    r"|\bmarketing\b"
    r"|\bnurse\b"
    r"|\bpflege\b"
    r"|\bdriver\b"
    r"|\bfahrer\b"
    r"|\bcook\b"
    r"|\bkoch\b"
    r"|\bwarehouse\b"
    r"|\blager\b"
    r"|\baccountant\b"
    r"|\bbuchhalter\b"
    r"|\blegal\b"
    r"|\bjurist\b"
    r"|\brecruiter\b"
    r"|\bhr\b"
    r"|\bteacher\b"
    r"|\blehrer\b"
    r"|\bcashier\b"
    r"|\bkassierer\b"
    r"|\bcleaner\b"
    r"|\breinigung\b"
    r"|\bmechanic\b"
    r"|\bmechaniker\b"
    r"|\belectrician\b"
    r"|\belektriker\b"
    r"|\belectrical\b"
    r"|\belectronics\b"
    r"|\belektro"           # prefisso: Elektrotechnik ecc.
    r"|\bmechanical\b"
    r"|\bcivil\b"
    r"|\bchemical\b"
    r"|\basic\b"
    r"|\bhardware\b"
    r"|\bux\b"
    r"|\bui\s+designer\b",
    re.IGNORECASE,
)
_BLACKLIST_OVERRIDE_RE = re.compile(r"\b(?:software|data|ai|it)\b", re.IGNORECASE)

# "product manager" vale solo se il titolo contiene junior/associate/assistant
_PM_RE = re.compile(r"\bproduct\s+manager\b", re.IGNORECASE)
_PM_QUALIFIER_RE = re.compile(r"\b(?:junior|associate|assistant)\b", re.IGNORECASE)

# Ciascuna tupla: (priorità, categoria, [pattern ...])
_PRIORITY_RULES: list[tuple[int, str, list[re.Pattern]]] = [
    (1, "analytics_ai", [
        re.compile(r"\bbusiness\s+analyst\b", re.IGNORECASE),
        re.compile(r"\brequirements(?:\s+engineer)?\b", re.IGNORECASE),
        re.compile(r"\bproduct\s+owner\b", re.IGNORECASE),
        re.compile(r"\bscrum\s+master\b", re.IGNORECASE),
        re.compile(r"\b(?:it|digital|technology)\s+consult(?:ant|ing)\b", re.IGNORECASE),
        re.compile(r"\bdata\s+analyst\b", re.IGNORECASE),
        re.compile(r"\b(?:bi|business\s+intelligence)\b", re.IGNORECASE),
        re.compile(r"\b(?:forecasting|demand\s+plan(?:ning|ner|s)?)\b", re.IGNORECASE),
        re.compile(r"\bsupply\s+chain\s+(?:analyst|analytics)\b", re.IGNORECASE),
        re.compile(r"\b(?:machine|reinforcement)\s+learning\b", re.IGNORECASE),
        re.compile(r"\bai\b", re.IGNORECASE),
        re.compile(r"\bresearch\s+(?:scientist|engineer)\b", re.IGNORECASE),
        re.compile(r"\bdata\s+(?:engineer|scientist|science)\b", re.IGNORECASE),
    ]),
    (2, "consulting_security", [
        re.compile(r"\bproject\s+(?:coordinator|assistant)\b", re.IGNORECASE),
        re.compile(r"\bpmo\b", re.IGNORECASE),
        re.compile(r"\bsecurity\s+analyst\b", re.IGNORECASE),
        re.compile(r"\bcybersecurity\b", re.IGNORECASE),
        re.compile(r"\bsoc\b", re.IGNORECASE),
        re.compile(r"\bsap\b", re.IGNORECASE),
        re.compile(r"\berp\b", re.IGNORECASE),
    ]),
    (3, "software", [
        re.compile(r"\bsoftware\s+(?:developer|engineer)\b", re.IGNORECASE),
        re.compile(r"\b(?:backend|back-end|frontend|front-end|fullstack|full-stack)\b", re.IGNORECASE),
        re.compile(r"\bweb\s+developer\b", re.IGNORECASE),
        re.compile(r"\bapplication\s+developer\b", re.IGNORECASE),
        re.compile(r"\bdevops\b", re.IGNORECASE),
    ]),
    (4, "support_qa", [
        re.compile(r"\bit\s+support\b", re.IGNORECASE),
        re.compile(r"\b(?:help\s+desk|helpdesk|service\s+desk|servicedesk)\b", re.IGNORECASE),
        re.compile(r"\bqa\b", re.IGNORECASE),
        re.compile(r"\btest\s+(?:analyst|automation)\b", re.IGNORECASE),
        re.compile(r"\btester\b", re.IGNORECASE),
    ]),
]


def role_category(title: str) -> tuple[str, int] | None:
    """Classifica il titolo in una categoria tech con priorità 1–5.

    Ritorna (categoria, priorità):
      1 analytics_ai  — data, AI, analytics, BI, forecasting
      2 consulting_security — SAP, ERP, cybersecurity, PMO
      3 software — software engineer/developer, backend, frontend, DevOps
      4 support_qa — IT support, QA, helpdesk, tester
      5 unclassified — nessun pattern riconosciuto ma nessuna parola non-tech
    Ritorna None se il titolo è chiaramente non tecnico (blacklist senza override).
    """
    if not title:
        return None
    if _PM_RE.search(title) and _PM_QUALIFIER_RE.search(title):
        return ("analytics_ai", 1)
    for priority, category, patterns in _PRIORITY_RULES:
        for pat in patterns:
            if pat.search(title):
                return (category, priority)
    if _BLACKLIST_RE.search(title) and not _BLACKLIST_OVERRIDE_RE.search(title):
        return None
    return ("unclassified", 5)


def is_tech_role(title: str) -> bool:
    return role_category(title) is not None


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
# Filtro paese
# ---------------------------------------------------------------------------

def country_ok(posting: dict) -> bool:
    """True se l'annuncio è geograficamente rilevante.

    - Paese vuoto → tieni (sconosciuto, dubbio pro-annuncio)
    - CH, DE, NL (ALLOWED_COUNTRIES) → sempre tieni
    - Remoto + paese in EUROPE_COUNTRIES → tieni
    - Altrimenti → scarta
    """
    country = posting.get("country_code") or ""
    if not country:
        return True
    if country in ALLOWED_COUNTRIES:
        return True
    work_mode = (posting.get("work_mode") or "").lower()
    if work_mode == "remote" and country in EUROPE_COUNTRIES:
        return True
    return False


# ---------------------------------------------------------------------------
# Pre-filtro combinato
# ---------------------------------------------------------------------------

def prefilter(postings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Applica country_ok, role_category e seniority_check a ogni annuncio.

    Ritorna (kept, discarded).
    - Discarded: chiave '_discard_reason'
    - Kept: chiavi '_role_category' e '_role_priority'
    """
    kept: list[dict] = []
    discarded: list[dict] = []

    for p in postings:
        title = p.get("title") or ""

        # 1. Paese
        if not country_ok(p):
            country = p.get("country_code") or "??"
            discarded.append({**p, "_discard_reason": f"paese non in lista ({country})"})
            continue

        # 2. Categoria ruolo tech
        rc = role_category(title)
        if rc is None:
            discarded.append({**p, "_discard_reason": "ruolo non tecnico"})
            continue

        # 3. Seniority — usa min_years_exp dal DB se disponibile
        min_ye_raw = p.get("min_years_exp")
        try:
            min_ye: int | None = int(min_ye_raw) if min_ye_raw is not None else None
        except (TypeError, ValueError):
            min_ye = None

        text = p.get("requirements_raw") or p.get("description") or ""
        is_incompatible, reason = seniority_check(title, text, min_years_exp=min_ye)
        if is_incompatible:
            discarded.append({**p, "_discard_reason": reason})
        else:
            kept.append({**p, "_role_category": rc[0], "_role_priority": rc[1]})

    kept.sort(key=lambda p: p["_role_priority"])
    return kept, discarded
