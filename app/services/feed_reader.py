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
    r"|\bvertrieb"          # radice: Vertriebsmitarbeiter, Außenvertrieb
    r"|\bverkauf"           # radice: Verkaufsgebiet, Verkäufer
    r"|\bmarketing\b"
    r"|\bnurse\b"
    r"|\bpflege"            # radice: Pflegehelfer, Altenpfleger
    r"|\bpersonal"          # radice: Personalentwicklung, Personalabteilung
    r"|\bdriver\b"
    r"|\bfahrer"            # radice: Busfahrer, Lkw-Fahrer
    r"|\bcook\b"
    r"|\bkoch"              # radice: Chefkoch, Hilfskoch
    r"|\bwarehouse\b"
    r"|\blager"             # radice: Lagermitarbeiter, Warenlager
    r"|\baccountant\b"
    r"|\bbuchhalt"          # radice: Buchhalter, Buchhaltung
    r"|\blegal\b"
    r"|\bjurist\b"
    r"|\brecruit"           # radice: Recruiter, Recruiting, Recruitment
    r"|\bhr\b"
    r"|\bteacher\b"
    r"|\blehrer\b"
    r"|\bcashier\b"
    r"|\bkassierer\b"
    r"|\bcleaner\b"
    r"|\breinigung"         # radice: Reinigungskraft, Gebäudereinigung
    r"|\bfacilit"           # radice: Facilitair, Facility, Facilitation
    r"|\bvorrat"            # radice: Vorratswirtschaft, Vorratsmanagement
    r"|\bdangerous\s+goods\b"
    r"|\bgefahrgut"
    r"|\bmedical\b"
    r"|\bfellow\b"
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

# Ruoli fuori bersaglio: commerciale, hardware, ingegneria di processo.
# Con queste parole nel titolo, "AI" o "data" da sole non bastano: né per la
# priorità 1 né per salvare il titolo dalla lista nera ("Account Executive,
# Leonardo.ai", "Hardware Systems Engineer - AI Hardware").
_NON_TARGET_RE = re.compile(
    # commerciale
    r"\baccount\b"             # Account Executive / Manager / Development Rep
    r"|\bsales\b"
    r"|\bvertrieb"
    r"|\bverkauf"
    r"|\bexecutive\b"
    r"|\brecruit"
    r"|\bmarketing\b"
    r"|\bseo\b"
    r"|\bbusiness\s+development\b"
    r"|\bcustomer\s+success\b"
    # hardware
    r"|\bhardware\b"
    r"|\basic\b"
    r"|\bfpga\b"
    # ingegneria di processo
    r"|\bprocess\s+(?:engineer\w*|control|technolog\w*)"
    r"|\bprozess(?:ingenieur|technik|technolog)\w*"
    r"|\bverfahrens\w*"
    r"|\bcvd\b",
    re.IGNORECASE,
)

# Parole-tema: dicono l'argomento, non il ruolo. Valgono la priorità 1 solo
# se il titolo non indica un altro ruolo (commerciale, hardware, processo,
# o una categoria 2–4 come "Software Engineer, AI Agents").
# (?<![.\w]) evita i nomi a dominio: "Leonardo.ai" non è un ruolo AI.
_P1_TOPIC_RE = re.compile(
    r"(?<![.\w])ai\b"
    r"|\bki\b"
    r"|\bml\b"
    r"|\b(?:machine|reinforcement|deep)\s+learning\b"
    r"|\bdata\s+science\b",
    re.IGNORECASE,
)

# Tesi e dottorati: non sono candidature da lavoro (vedi posting_kind).
_THESIS_RE = re.compile(
    r"\bph\.?\s?d\b"
    r"|\bpromotion\b"
    r"|\bdoktorarbeit\w*"
    r"|\bdoktorand\w*"
    r"|\bdissertation\b"
    r"|\bdoctoral\b"
    r"|\bthesis\b"
    r"|\b(?:master|bachelor)thesis\b"
    r"|\b(?:master|bachelor|abschluss|diplom)arbeit\w*"
    r"|\bafstudeer\w*"
    r"|\btesi\b"
    r"|\bdottorato\b",
    re.IGNORECASE,
)

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
        re.compile(r"\bresearch\s+(?:scientist|engineer)\b", re.IGNORECASE),
        re.compile(r"\bdata\s+(?:engineer|scientist)\b", re.IGNORECASE),
        # ruolo AI/ML esplicito: "AI Engineer", "Machine Learning Researcher"
        re.compile(
            r"(?<![.\w])(?:ai|ki|ml|(?:machine|reinforcement|deep)\s+learning)\s+"
            r"(?:engineer|scientist|researcher|research|developer|entwickler|analyst|consultant)\b",
            re.IGNORECASE,
        ),
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

    La priorità 1 richiede che il TITOLO indichi il ruolo (analyst, product
    owner, data engineer, AI researcher...). Le parole-tema (AI, ML, data
    science) da sole valgono la priorità 1 solo se il titolo non indica un
    altro ruolo: con un ruolo commerciale, hardware o di processo l'annuncio
    è scartato, con un ruolo delle categorie 2–4 prende quella categoria.
    """
    if not title:
        return None
    if _PM_RE.search(title) and _PM_QUALIFIER_RE.search(title):
        return ("analytics_ai", 1)

    matched: tuple[str, int] | None = None
    for priority, category, patterns in _PRIORITY_RULES:
        if any(pat.search(title) for pat in patterns):
            matched = (category, priority)
            break
    if matched and matched[1] == 1:
        return matched

    if _NON_TARGET_RE.search(title):
        # "Software Engineer, Sales Tools" resta un ruolo software;
        # tutto il resto è commerciale/hardware/processo → fuori.
        return matched if matched and matched[0] == "software" else None
    if matched:
        return matched
    if _P1_TOPIC_RE.search(title):
        return ("analytics_ai", 1)
    if _BLACKLIST_RE.search(title) and not _BLACKLIST_OVERRIDE_RE.search(title):
        return None
    return ("unclassified", 5)


def posting_kind(title: str) -> str:
    """Ritorna "thesis" per tesi e dottorati (PhD, Promotion, Masterarbeit,
    Thesis...) e "job" per tutto il resto. Le tesi non si scartano: si
    marcano, così la pagina le può tenere fuori dalla lista principale."""
    return "thesis" if _THESIS_RE.search(title or "") else "job"


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

REGION_REMOTE_EUROPE = "remote_eu"
REGION_UNKNOWN = "unknown"

# La località parla di tutta l'Europa...
_EUROPE_WIDE_RE = re.compile(r"\b(?:europe|europa|european|emea|eu|dach)\b", re.IGNORECASE)
# ...o nomina uno dei paesi richiesti (o una loro città principale).
_ALLOWED_PLACE_RE = re.compile(
    r"\b(?:germany|deutschland|germania|switzerland|schweiz|suisse|svizzera"
    r"|netherlands|nederland|holland|paesi\s+bassi"
    r"|berlin|munich|münchen|hamburg|frankfurt|cologne|köln|stuttgart|düsseldorf"
    r"|zurich|zürich|geneva|genf|basel|bern|lausanne"
    r"|amsterdam|rotterdam|eindhoven|utrecht|den\s+haag|the\s+hague)\b",
    re.IGNORECASE,
)
# Località che nomina in chiaro un paese (o un'area) non richiesto. Serve
# solo per gli annunci senza country_code: "United States (Remote)" ha il
# paese indicato, anche se non nel campo giusto. L'elenco è volutamente
# corto: ciò che non riconosce resta tra i "paese non indicato".
_FOREIGN_PLACE_RE = re.compile(
    r"\b(?:united\s+states|usa|america|americas|north\s+america|namer|latam|canada"
    r"|california|washington|new\s+york|nyc|san\s+francisco|bay\s+area|mountain\s+view"
    r"|virginia|maryland|colorado|texas|boston|seattle|toronto|montreal"
    r"|mexico|brazil|brasil|costa\s+rica|argentina"
    r"|united\s+kingdom|uk|england|london|ireland|dublin|france|paris|spain|madrid|barcelona"
    r"|italy|poland|portugal|sweden|denmark|norway|finland"
    r"|apac|asia|india|bengaluru|bangalore|gurugram|philippines|manila|korea|seoul|taiwan|taipei"
    r"|japan|tokyo|china|singapore|indonesia|australia|sydney|melbourne"
    r"|kuwait|qatar|doha|ksa|saudi|uae|dubai|israel)\b",
    re.IGNORECASE,
)
# "US" solo in maiuscolo: "Remote US" sì, il pronome "us" no.
_US_CODE_RE = re.compile(r"\bUS\b")


def posting_region(posting: dict) -> str | None:
    """Dove si lavora, ai fini del filtro. None = annuncio da scartare.

    - CH, DE, NL → il codice paese
    - Altro paese europeo → "remote_eu" solo se l'annuncio è remoto E la
      località parla di Europa/EMEA o nomina un paese richiesto
      ("Remote, Europe", "United Kingdom, Germany, Netherlands").
      "Remote, United Kingdom" o "Remote, Spain" sono lavori in quel paese
      → scartati, come tutti gli altri paesi non richiesti.
    - Paese non indicato → "unknown" (si tiene: meglio un falso positivo),
      a meno che la località nomini in chiaro solo paesi non richiesti
      ("United States (Remote)", "Manila, Philippines").
    """
    country = (posting.get("country_code") or "").strip().upper()
    location = posting.get("location") or ""
    # "Europa" può stare anche nel titolo: "ML Engineer - EMEA Remote"
    in_scope = bool(
        _EUROPE_WIDE_RE.search(location)
        or _ALLOWED_PLACE_RE.search(location)
        or _EUROPE_WIDE_RE.search(posting.get("title") or "")
    )

    if country in ALLOWED_COUNTRIES:
        return country
    if not country:
        foreign = _FOREIGN_PLACE_RE.search(location) or _US_CODE_RE.search(location)
        if foreign and not in_scope:
            return None
        return REGION_UNKNOWN
    work_mode = (posting.get("work_mode") or "").lower()
    if work_mode == "remote" and country in EUROPE_COUNTRIES and in_scope:
        return REGION_REMOTE_EUROPE
    return None


def country_ok(posting: dict) -> bool:
    """True se l'annuncio è geograficamente rilevante (vedi posting_region)."""
    return posting_region(posting) is not None


# ---------------------------------------------------------------------------
# Pre-filtro combinato
# ---------------------------------------------------------------------------

def prefilter(postings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Applica country_ok, role_category e seniority_check a ogni annuncio.

    Ritorna (kept, discarded).
    - Discarded: chiave '_discard_reason'
    - Kept: chiavi '_role_category', '_role_priority', '_region' (CH/DE/NL,
      "remote_eu" o "unknown") e '_kind' ("job" o "thesis")
    """
    kept: list[dict] = []
    discarded: list[dict] = []

    for p in postings:
        title = p.get("title") or ""

        # 1. Paese
        region = posting_region(p)
        if region is None:
            country = p.get("country_code") or p.get("location") or "??"
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
            kept.append({
                **p,
                "_role_category": rc[0],
                "_role_priority": rc[1],
                "_region": region,
                "_kind": posting_kind(title),
            })

    kept.sort(key=lambda p: p["_role_priority"])
    return kept, discarded
