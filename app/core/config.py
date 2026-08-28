"""
Configurazione centrale del sistema.

Contiene il dizionario dei job board per paese (RF3.1a) e tutte le
impostazioni caricate da variabili d'ambiente.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/job_matcher.db")

# ---------------------------------------------------------------------
# LLM providers
# ---------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
LLM_CACHE_ENABLED = os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------------------
# Google Places (opzionale — se assente si usa solo LLM + scraping)
# ---------------------------------------------------------------------
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
PLACES_TEXTSEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

# ---------------------------------------------------------------------
# Scraper — rate limiting (R03)
# ---------------------------------------------------------------------
SCRAPER_DELAY_MIN = float(os.getenv("SCRAPER_DELAY_MIN", "3.0"))
SCRAPER_DELAY_MAX = float(os.getenv("SCRAPER_DELAY_MAX", "8.0"))
SCRAPER_TIMEOUT = float(os.getenv("SCRAPER_TIMEOUT", "20"))
SCRAPER_MAX_LISTINGS_PER_SOURCE = int(os.getenv("SCRAPER_MAX_LISTINGS_PER_SOURCE", "10"))

# Il delay 3-8s va rispettato PER HOST, non globalmente: interrogare 21
# portali su 21 domini diversi uno alla volta significa aspettare ~2 minuti
# per una cortesia che nessuno dei 21 percepisce. Questo è il numero massimo
# di richieste in volo contemporaneamente, su host diversi.
SCRAPER_MAX_CONCURRENCY = int(os.getenv("SCRAPER_MAX_CONCURRENCY", "8"))

# Delay più breve per sondare la careers page sul sito di un'azienda.
# Il 3-8s esiste per i grandi job board con sistemi anti-bot; applicarlo
# anche agli 8 tentativi di path su un normale sito aziendale costava fino
# a ~44 secondi per azienda solo per scoprire un URL.
SCRAPER_PROBE_DELAY_MIN = float(os.getenv("SCRAPER_PROBE_DELAY_MIN", "0.5"))
SCRAPER_PROBE_DELAY_MAX = float(os.getenv("SCRAPER_PROBE_DELAY_MAX", "1.5"))

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# ---------------------------------------------------------------------
# RF3.1a — Job board per paese
#
# I board "global" vengono sempre inclusi nella rotazione.
# Quelli specifici del paese si aggiungono in base a
# SearchSession.preferred_country.
#
# Campo "style" — dove finiscono {q} e {loc} nell'URL:
#   "query" (default) → in una query string, si codifica con quote_plus
#   "path"            → in un segmento di path, si codifica come slug
# La distinzione non è cosmetica: in un path segment il "+" prodotto da
# quote_plus è un carattere letterale, non uno spazio, quindi gli URL dei
# board "path" costruiti con quote_plus sono strutturalmente sbagliati.
# Vedi ScraperEngine.build_board_url.
#
# Campo "template_no_loc" — variante da usare quando la località è vuota,
# perché per i board "path" un {loc} vuoto lascia l'URL troncato
# (es. ".../data-analyst-jobs-in-").
# ---------------------------------------------------------------------
JOB_BOARDS: dict[str, list[dict]] = {
    "global": [
        {"name": "LinkedIn", "url_template": "https://www.linkedin.com/jobs/search?keywords={q}&location={loc}"},
       # {"name": "Indeed", "url_template": "https://www.indeed.com/jobs?q={q}&l={loc}"},
       # {"name": "Glassdoor", "url_template": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={q}&locT=C&locKeyword={loc}"},
    ],
    "IT": [
        # il path /lavoro non esiste più su Indeed Italia: oggi è /jobs.
        # NB: corretto ma insufficiente — Indeed risponde comunque 403 allo
        # scraping HTTP semplice, su tutte le varianti nazionali.
        {"name": "Indeed IT", "url_template": "https://it.indeed.com/jobs?q={q}&l={loc}"},
        # InfoJobs.it RIMOSSO: la piattaforma è stata chiusa definitivamente.
        # Risponde 200 con una pagina di commiato ("Questa piattaforma è
        # ufficialmente chiusa e non più disponibile"), quindi superava la
        # soglia dei 100 caratteri e costava una chiamata LLM a ogni ricerca
        # per farsi dire che non esiste più. Da non reintrodurre.
        # (InfoJobs ES sotto è un'altra società ed è ancora attiva.)
        {"name": "Monster IT", "url_template": "https://www.monster.it/lavoro/cerca?q={q}&where={loc}"},
    ],
    "CH": [
        {"name": "jobs.ch", "url_template": "https://www.jobs.ch/en/vacancies/?term={q}&location={loc}"},
        {"name": "jobup.ch", "url_template": "https://www.jobup.ch/en/jobs/?term={q}&location={loc}"},
        {"name": "JobScout24", "url_template": "https://www.jobscout24.ch/de/jobs/?q={q}&l={loc}"},
    ],
    "DE": [
        {"name": "StepStone", "style": "path",
         "url_template": "https://www.stepstone.de/jobs/{q}/in-{loc}",
         "template_no_loc": "https://www.stepstone.de/jobs/{q}"},
        {"name": "Indeed DE", "url_template": "https://de.indeed.com/jobs?q={q}&l={loc}"},
        {"name": "Xing", "url_template": "https://www.xing.com/jobs/search?keywords={q}&location={loc}"},
    ],
    "AT": [
        {"name": "karriere.at", "style": "path",
         "url_template": "https://www.karriere.at/jobs/{q}/{loc}",
         "template_no_loc": "https://www.karriere.at/jobs/{q}"},
        {"name": "Indeed AT", "url_template": "https://at.indeed.com/jobs?q={q}&l={loc}"},
    ],
    "FR": [
        {"name": "Indeed FR", "url_template": "https://fr.indeed.com/emplois?q={q}&l={loc}"},
        {"name": "APEC", "url_template": "https://www.apec.fr/candidat/recherche-emploi.html?motsCles={q}&lieux={loc}"},
    ],
    "UK": [
        {"name": "Reed", "style": "path",
         "url_template": "https://www.reed.co.uk/jobs/{q}-jobs-in-{loc}",
         "template_no_loc": "https://www.reed.co.uk/jobs/{q}-jobs"},
        {"name": "TotalJobs", "style": "path",
         "url_template": "https://www.totaljobs.com/jobs/{q}/in-{loc}",
         "template_no_loc": "https://www.totaljobs.com/jobs/{q}"},
        {"name": "Indeed UK", "url_template": "https://uk.indeed.com/jobs?q={q}&l={loc}"},
    ],
    "US": [
        # NB: stesso url_template di "Indeed" global — la dedup in
        # get_boards_for_country lo scarta invece di scaricarlo due volte
        {"name": "Indeed US", "url_template": "https://www.indeed.com/jobs?q={q}&l={loc}"},
        {"name": "ZipRecruiter", "url_template": "https://www.ziprecruiter.com/jobs-search?search={q}&location={loc}"},
        {"name": "Dice", "url_template": "https://www.dice.com/jobs?q={q}&location={loc}"},
    ],
    "ES": [
        {"name": "InfoJobs ES", "url_template": "https://www.infojobs.net/jobsearch/search-results/list.xhtml?keyword={q}&province={loc}"},
        {"name": "Indeed ES", "url_template": "https://es.indeed.com/trabajo?q={q}&l={loc}"},
    ],
}


# RF... — "Europa" aggrega i board dei paesi europei già configurati
# sopra, invece di richiedere l'integrazione di nuovi portali paneuropei.
EUROPEAN_COUNTRY_CODES = ["IT", "CH", "DE", "AT", "FR", "ES", "UK"]

# Il nome del paese da mandare ai portali globali vive in app/data/geo.json
# (campo "search_name") e si legge con app.services.geo.search_name().
#
# È IN INGLESE, e non è un dettaglio estetico: LinkedIn, Indeed e Glassdoor
# risolvono la località contro un database geografico anglofono, e un nome
# che non riconoscono non produce un errore — li fa ricadere sul default,
# che sono gli Stati Uniti. Misurato cercando "Data Analyst" su LinkedIn,
# contando i riferimenti a luoghi italiani e statunitensi nella pagina:
#
#   location=          ->  IT   0   US  77
#   location=Italia    ->  IT   1   US  77     <- il nome nativo NON funziona
#   location=Italy     ->  IT  97   US   0     <- quello inglese sì
#   location=Europe    ->  EU  21   US   0
#
# È la spiegazione di un fatto misurato sul database reale: 0 annunci su 249
# avevano mai avuto una sede italiana, comprese quattro ricerche impostate
# su Italia. Non era un problema di aziende: era la località che non
# arrivava mai ai portali in una forma che sapessero leggere.

API_TOKEN = os.getenv("API_TOKEN", "local-dev-token-2026")

def _is_valid_board(board: dict) -> bool:
    """Una riga malformata non deve far fallire l'intera ricerca.

    Senza questo controllo un refuso nel template (una graffa di troppo,
    una chiave mancante) solleverebbe KeyError/IndexError dentro
    search_job_boards, l'eccezione risalirebbe fino a run_search e la
    sessione finirebbe in status="error" — per un errore di battitura in
    un dizionario di configurazione."""
    if not isinstance(board, dict):
        return False
    name, template = board.get("name"), board.get("url_template")
    if not name or not template:
        return False
    try:
        template.format(q="test", loc="test")
        if board.get("template_no_loc"):
            board["template_no_loc"].format(q="test")
    except (KeyError, IndexError, ValueError):
        logger.warning("Board '%s' ignorato: template non valido (%s)", name, template)
        return False
    return True


def get_boards_for_country(country: str | None) -> list[dict]:
    """RF3.1a + RF3.3 — restituisce i board globali più quelli del paese
    (o, per "EU", quelli di tutti i paesi europei configurati).

    Dedup per url_template oltre che per nome: alcuni board sono elencati
    due volte con nomi diversi ma stesso URL (es. "Indeed" global e
    "Indeed US"), e scaricare due volte la stessa pagina costa un delay
    e una chiamata LLM per niente."""
    boards: list[dict] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()

    def _accumulate(candidates: list[dict], code: str | None) -> None:
        for board in candidates:
            if not _is_valid_board(board):
                continue
            if board["name"] in seen_names or board["url_template"] in seen_urls:
                continue
            seen_names.add(board["name"])
            seen_urls.add(board["url_template"])
            # copia: il codice paese serve a decidere che località mandare a
            # questo board, ma non va scritto sul dizionario condiviso
            boards.append(dict(board, country=code))

    _accumulate(JOB_BOARDS["global"], None)
    if not country:
        return boards

    codes = EUROPEAN_COUNTRY_CODES if country.upper() == "EU" else [country.upper()]
    for code in codes:
        _accumulate(JOB_BOARDS.get(code, []), code)
    return boards


# ---------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------
DEFAULT_MATCH_THRESHOLD = float(os.getenv("DEFAULT_MATCH_THRESHOLD", "0.5"))

# ---------------------------------------------------------------------
# Cache annunci — per quante ore i dati di un'azienda restano "freschi".
# Entro questa finestra una nuova ricerca sulla stessa azienda non tocca la
# rete: riusa quanto già raccolto, anche se a raccoglierlo era stata
# un'altra sessione. Il matching resta comunque per-utente — è lì che sta la
# personalizzazione, non nella raccolta.
# 0 disabilita il riuso (utile per il debug).
# ---------------------------------------------------------------------
LISTING_TTL_HOURS = int(os.getenv("LISTING_TTL_HOURS", "24"))

# Tetto agli annunci presi da un singolo feed ATS. Un feed aziendale è il
# catalogo COMPLETO delle posizioni aperte (Datadog ne espone 429), non una
# ricerca già filtrata come quella di un portale: senza un tetto una sola
# azienda riempirebbe la sessione. Si applica dopo il filtro per ruolo.
ATS_MAX_LISTINGS_PER_COMPANY = int(os.getenv("ATS_MAX_LISTINGS_PER_COMPANY", "40"))

# Dopo quanti giorni riprovare a cercare l'ATS di un'azienda per cui la
# ricerca era fallita. Senza scadenza il fallimento sarebbe definitivo:
# un'azienda che adotta Greenhouse il mese dopo resterebbe per sempre sul
# percorso costoso (scraping + LLM).
ATS_REPROBE_DAYS = int(os.getenv("ATS_REPROBE_DAYS", "30"))
# peso del keyword-matching vs analisi semantica LLM nello score finale
KEYWORD_WEIGHT = float(os.getenv("KEYWORD_WEIGHT", "0.4"))
SEMANTIC_WEIGHT = float(os.getenv("SEMANTIC_WEIGHT", "0.6"))

# ---------------------------------------------------------------------
# Poller — Livello 1 del brainstorming pub/sub (vedi piano in
# .claude/plans e docs/DECISIONS.md). Ricontrolla periodicamente le
# careers page già verificate delle sessioni concluse, per accorgersi di
# annunci nuovi usciti dopo l'ultima ricerca manuale. Notifica pull-based
# (badge "+N nuovi" nella lista sessioni), non push — vedi search_runner.py.
#
# Disabilitato di default: consuma quota LLM in background anche quando
# non stai usando l'app — va acceso consapevolmente.
# ---------------------------------------------------------------------
POLL_ENABLED = os.getenv("POLL_ENABLED", "false").lower() == "true"
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "3600"))
