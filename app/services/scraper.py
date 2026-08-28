"""
ScraperEngine — raccolta annunci da job board e careers page.

Mitigazioni implementate:
  R01 — rotazione tra sorgenti: nessun board riceve traffico concentrato
  R02 — parsing LLM-based: non usa selettori CSS, non si rompe al
        cambio di layout
  R03 — rate limiting: delay randomizzato 3–8s + user-agent rotation
  R08 — deduplicazione per hash del contenuto
"""
import asyncio
import hashlib
import logging
import random
import re
import unicodedata
from urllib.parse import quote, quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import (
    SCRAPER_DELAY_MAX,
    SCRAPER_DELAY_MIN,
    SCRAPER_MAX_CONCURRENCY,
    SCRAPER_MAX_LISTINGS_PER_SOURCE,
    SCRAPER_PROBE_DELAY_MAX,
    SCRAPER_PROBE_DELAY_MIN,
    SCRAPER_TIMEOUT,
    USER_AGENTS,
    get_boards_for_country,
)
from app.services import geo
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

# Due profili di cortesia: i job board hanno sistemi anti-bot, il sito di
# un'azienda no. Vedi SCRAPER_PROBE_DELAY_* in config.py.
BOARD_DELAY = (SCRAPER_DELAY_MIN, SCRAPER_DELAY_MAX)
PROBE_DELAY = (SCRAPER_PROBE_DELAY_MIN, SCRAPER_PROBE_DELAY_MAX)

CAREERS_PATHS = [
    "/careers",
    "/carriere",
    "/jobs",
    "/lavora-con-noi",
    "/work-with-us",
    "/join-us",
    "/en/careers",
    "/about/careers",
]

# limite testo passato all'LLM per l'estrazione annunci — alzato leggermente
# rispetto agli 8000 originali per fare spazio agli URL inlineati (vedi
# _strip_html), in tensione diretta con la quota LLM (più testo = più costo)
MAX_PAGE_CHARS = 10000

# Frasi che compaiono solo nelle pagine di blocco anti-bot o di chiusura
# servizio, mai in una pagina di annunci vera. Un 403 viene già scartato da
# raise_for_status senza costi, ma alcuni portali rispondono 200 con una
# challenge page di migliaia di caratteri: supera la soglia dei 100 char e
# costa una chiamata LLM per farsi dire che siamo stati bloccati.
# Volutamente specifiche: "javascript" da solo comparirebbe in qualunque
# annuncio per sviluppatori.
BLOCKED_PAGE_MARKERS = (
    "verify you are human",
    "humans only",
    "riservato agli umani",
    "réservé aux humains",
    "checking your browser",
    "unusual traffic",
    "captcha",
    "access to this page has been denied",
    "ufficialmente chiusa",
    "enable javascript to continue",
)


class ScraperEngine:
    def __init__(self, llm: LLMGateway):
        self.llm = llm
        # R03 — il delay è per host: due domini diversi non si aspettano
        # a vicenda, due richieste allo stesso dominio sì.
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._host_last_request: dict[str, float] = {}
        self._semaphore = asyncio.Semaphore(SCRAPER_MAX_CONCURRENCY)

    # -----------------------------------------------------------------
    # R03 — rate limiting per host
    # -----------------------------------------------------------------
    def _host_lock(self, host: str) -> asyncio.Lock:
        lock = self._host_locks.get(host)
        if lock is None:
            lock = self._host_locks[host] = asyncio.Lock()
        return lock

    async def _throttle(self, url: str, delay: tuple[float, float]) -> None:
        """Garantisce un intervallo minimo tra due richieste allo STESSO
        host, senza far aspettare gli altri.

        Il lock viene tenuto durante l'attesa proprio per serializzare le
        richieste a quel dominio: è la cortesia che conta. La prima
        richiesta a un host non attende — non c'è nessuno da non
        disturbare."""
        host = urlparse(url).netloc
        loop = asyncio.get_running_loop()
        async with self._host_lock(host):
            last = self._host_last_request.get(host)
            if last is not None:
                wait = random.uniform(*delay) - (loop.time() - last)
                if wait > 0:
                    await asyncio.sleep(wait)
            self._host_last_request[host] = loop.time()

    @staticmethod
    def _headers() -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        }

    async def _fetch(
        self, url: str, delay: tuple[float, float] | None = None
    ) -> tuple[str | None, dict]:
        """Ritorna (html, diagnostica). La diagnostica viaggia nel valore di
        ritorno e non su `self` di proposito: le richieste sono concorrenti,
        uno stato condiviso sull'istanza verrebbe sovrascritto da un'altra
        coroutine prima di essere letto."""
        diag: dict = {"status": None, "bytes": 0, "error": None}
        try:
            await self._throttle(url, delay or BOARD_DELAY)
            async with self._semaphore:
                async with httpx.AsyncClient(
                    timeout=SCRAPER_TIMEOUT, follow_redirects=True
                ) as client:
                    resp = await client.get(url, headers=self._headers())
                    diag["status"] = resp.status_code
                    diag["bytes"] = len(resp.content)
                    resp.raise_for_status()
                    return resp.text, diag
        except asyncio.CancelledError:
            raise  # la cancellazione della ricerca non è un errore di fetch
        except Exception as exc:  # noqa: BLE001
            diag["error"] = f"{type(exc).__name__}: {exc}"
            logger.info("Fetch fallito %s: %s", url, exc)
            return None, diag

    @staticmethod
    def _strip_html(html: str, base_url: str) -> str:
        """Ripulisce l'HTML per l'LLM MA preserva i link (a differenza della
        versione precedente, che li buttava via con get_text()) — altrimenti
        l'LLM non può mai sapere l'URL specifico di un annuncio, solo quello
        della pagina intera (bug scoperto: ogni annuncio finiva con lo stesso
        source_url, quello della pagina di ricerca).

        Ordine importante: si eliminano PRIMA nav/footer/header/script (così
        i loro link non finiscono inlineati nel testo come rumore), POI si
        inlineano i link superstiti nel formato "testo (URL: ...)"."""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "svg", "noscript"]):
            tag.decompose()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("javascript:", "#", "mailto:")):
                continue
            absolute = urljoin(base_url, href)
            link_text = a.get_text(strip=True)
            a.replace_with(f"{link_text} (URL: {absolute})" if link_text else f"(URL: {absolute})")

        return soup.get_text(separator="\n", strip=True)

    # -----------------------------------------------------------------
    # Costruzione URL dei board
    # -----------------------------------------------------------------
    @staticmethod
    def _slug(value: str) -> str:
        """Codifica per un segmento di path: minuscolo, accenti rimossi,
        spazi e punteggiatura ridotti a trattini.

        Serve perché quote_plus produce "+" per gli spazi, e in un path
        segment il "+" è un carattere letterale — non uno spazio. Gli URL
        di StepStone, karriere.at, Reed e TotalJobs mettono {q} e {loc}
        nel path, quindi con quote_plus cercavano letteralmente
        "data+analyst" invece di "data analyst"."""
        normalized = unicodedata.normalize("NFKD", value)
        ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
        return quote(slug, safe="-")

    @staticmethod
    def effective_location(
        board: dict, location: str | None, country: str | None
    ) -> str:
        """Quale località mandare a QUESTO board.

        Un portale nazionale (jobs.ch, karriere.at) con località vuota
        restituisce il proprio paese: è già il comportamento giusto, e
        mandargli una zona di un altro paese sarebbe solo rumore — con
        Paese="EU" chiedere "Marche" a jobs.ch non ha senso.

        Un portale GLOBALE (LinkedIn, Indeed, Glassdoor) con località vuota
        invece non restituisce "il mondo": restituisce il suo default, che
        è tipicamente gli Stati Uniti. È il motivo per cui nessuna ricerca
        impostata sull'Italia aveva mai prodotto un annuncio italiano.
        A quelli si manda sempre qualcosa, e il più specifico possibile:
        "Marche, Italia" funziona molto meglio del solo "Italia"."""
        zona = (location or "").strip()
        board_country = board.get("country")

        if board_country:
            # portale nazionale: la zona vale solo se siamo nel suo paese
            same = country and country.upper() == board_country.upper()
            return zona if (zona and same) else ""

        paese = geo.search_name(country)
        if zona and paese:
            return f"{zona}, {paese}"
        return zona or paese or ""

    @staticmethod
    def build_board_url(
        board: dict, role_title: str, location: str | None, country: str | None = None
    ) -> str:
        """Applica al template l'encoding giusto per il tipo di board.

        Se la località è vuota e il board dichiara un template
        alternativo, usa quello: per i board "path" un {loc} vuoto
        lascerebbe l'URL troncato (es. ".../data-analyst-jobs-in-")."""
        loc = ScraperEngine.effective_location(board, location, country)
        if not loc and board.get("template_no_loc"):
            return board["template_no_loc"].format(q=ScraperEngine._encode(board, role_title))

        encode = ScraperEngine._encode
        return board["url_template"].format(
            q=encode(board, role_title), loc=encode(board, loc)
        )

    @staticmethod
    def _encode(board: dict, value: str) -> str:
        if board.get("style") == "path":
            return ScraperEngine._slug(value)
        return quote_plus(value)

    @staticmethod
    def content_hash(title: str, company: str, requirements: str) -> str:
        """R08 — dedup: stesso annuncio da fonti diverse produce lo stesso hash."""
        norm = f"{title.lower().strip()}|{company.lower().strip()}|{(requirements or '')[:500].lower().strip()}"
        return hashlib.sha256(norm.encode()).hexdigest()

    # -----------------------------------------------------------------
    # RF3.1b — trova la careers page di un'azienda dinamicamente
    # -----------------------------------------------------------------
    async def find_careers_url(self, company_name: str, website: str | None) -> str | None:
        """Prova i path standard sul sito aziendale. Se il sito non è
        noto, chiede all'LLM di indovinare il dominio e verifica."""
        if not website:
            website = await self._guess_website(company_name)
        if not website:
            return None

        if not website.startswith("http"):
            website = f"https://{website}"

        parsed = urlparse(website)
        base = f"{parsed.scheme}://{parsed.netloc}"

        # Gli 8 path stanno tutti sullo stesso host: parallelizzarli
        # significherebbe martellare il sito dell'azienda, e il throttling
        # per host li serializzerebbe comunque. Il guadagno viene dal delay
        # più breve (PROBE_DELAY) — il 3-8s serve contro gli anti-bot dei
        # grandi portali, non per la careers page di un'azienda — e dal
        # fermarsi al primo path buono. Prima: fino a ~44s per azienda.
        for path in CAREERS_PATHS:
            url = urljoin(base, path)
            html, _diag = await self._fetch(url, delay=PROBE_DELAY)
            if html and self._looks_like_careers_page(html):
                logger.info("Careers page trovata per %s: %s", company_name, url)
                return url
        return None

    async def _guess_website(self, company_name: str) -> str | None:
        prompt = (
            f"Qual è il dominio del sito web ufficiale dell'azienda '{company_name}'? "
            'Rispondi SOLO con un oggetto JSON: {"domain": "esempio.com"} '
            'oppure {"domain": null} se non lo conosci con certezza.'
        )
        data = await self.llm.complete_json(prompt, default=None)
        if isinstance(data, dict):
            domain = data.get("domain")
            if domain and isinstance(domain, str) and "." in domain:
                return domain.strip()
        return None

    @staticmethod
    def _blocked_page_marker(text: str) -> str | None:
        """Ritorna il marcatore trovato, o None. Cerca solo nei primi 3000
        caratteri: le challenge page dicono subito cosa sono, mentre una
        pagina di annunci lunga potrebbe contenere per caso una di queste
        frasi molto più in basso."""
        head = text[:3000].lower()
        return next((m for m in BLOCKED_PAGE_MARKERS if m in head), None)

    @staticmethod
    def _looks_like_careers_page(html: str) -> bool:
        text = html.lower()
        markers = ["career", "posizioni aperte", "job openings", "lavora con noi",
                   "open positions", "vacancies", "offerte di lavoro", "we're hiring"]
        return any(m in text for m in markers)

    # -----------------------------------------------------------------
    # R02 — parsing LLM-based degli annunci
    # -----------------------------------------------------------------
    async def extract_listings_from_page(
        self, url: str, company_name: str, source_board: str
    ) -> list[dict]:
        listings, _diag = await self.extract_with_diagnostics(
            url, company_name, source_board
        )
        return listings

    async def extract_with_diagnostics(
        self, url: str, company_name: str, source_board: str
    ) -> tuple[list[dict], dict]:
        """Come extract_listings_from_page, ma riporta anche perché una
        pagina non ha prodotto annunci: senza questo, un board che risponde
        403 e uno che risponde 200 con una shell JavaScript vuota sono
        indistinguibili nel log — entrambi "0 annunci"."""
        html, diag = await self._fetch(url)
        diag["url"] = url
        diag["listings"] = 0
        if not html:
            diag["outcome"] = "fetch_failed"
            return [], diag

        raw_text = self._strip_html(html, url)
        diag["text_chars"] = len(raw_text)
        if len(raw_text) < 100:
            # nessuna chiamata LLM: pagina vuota o renderizzata lato client
            diag["outcome"] = "empty_page"
            return [], diag

        blocker = self._blocked_page_marker(raw_text)
        if blocker:
            diag["outcome"] = f"blocked_page ({blocker})"
            return [], diag

        page_text = raw_text[:MAX_PAGE_CHARS]

        prompt = (
            "Analizza il testo di questa pagina e estrai TUTTI gli annunci di lavoro presenti.\n"
            "Il testo contiene link inlineati nel formato \"testo (URL: https://...)\".\n"
            "Per ogni annuncio restituisci un oggetto con queste chiavi esatte:\n"
            '  "title": titolo della posizione\n'
            '  "location": sede di lavoro (null se assente)\n'
            '  "contract_type": tipo contratto (null se assente)\n'
            '  "requirements_raw": requisiti e competenze richieste, testo integrale\n'
            '  "description": breve descrizione del ruolo\n'
            '  "posted_date": data pubblicazione (null se assente)\n'
            '  "url": il link diretto a QUESTO specifico annuncio, cercandolo tra i '
            '"(URL: ...)" più vicini al titolo — copialo esattamente come appare nel '
            'testo, non modificarlo. null se non trovi un link plausibile per questo annuncio.\n\n'
            "Rispondi SOLO con un array JSON. Se non trovi annunci rispondi [].\n"
            "Non inventare annunci che non sono nel testo. Non inventare URL: usa SOLO "
            "un URL copiato letteralmente dal testo fornito.\n\n"
            f"TESTO PAGINA:\n{page_text}"
        )

        listings = await self.llm.complete_json(prompt, default=[])
        diag["llm_called"] = True
        if not isinstance(listings, list):
            diag["outcome"] = "llm_no_array"
            return [], diag

        out: list[dict] = []
        for item in listings[:SCRAPER_MAX_LISTINGS_PER_SOURCE]:
            if not isinstance(item, dict) or not item.get("title"):
                continue
            item_url = item.get("url")
            # validazione leggera contro allucinazioni (coerente con l'approccio
            # già usato per le aziende, ADR-006): l'URL è valido solo se compare
            # letteralmente nel testo che l'LLM ha davvero visto, altrimenti si
            # ripiega sull'URL della pagina intera (comportamento precedente)
            if not (isinstance(item_url, str) and item_url.strip() and item_url in page_text):
                item_url = url
            item["company_name"] = company_name
            item["source_url"] = item_url
            item["source_board"] = source_board
            out.append(item)

        diag["listings"] = len(out)
        diag["outcome"] = "ok" if out else "no_listings_in_page"
        return out, diag

    # -----------------------------------------------------------------
    # RF3.1a — ricerca sui job board con rotazione
    # -----------------------------------------------------------------
    async def search_job_boards(
        self,
        role_title: str,
        location: str | None,
        country: str | None,
        on_board_result=None,
    ) -> list[dict]:
        """Interroga i board globali + quelli del paese in parallelo.

        Il rate limiting resta rispettato: `_throttle` serializza le
        richieste per host, quindi la concorrenza gioca solo tra domini
        diversi. Prima erano seriali anche tra host diversi — 21 board
        significavano ~2 minuti di sole attese.

        `on_board_result(board_name, diag)` viene chiamata per ogni portale
        con l'esito (status HTTP, byte, annunci estratti): serve a rendere
        la salute dei board un dato osservabile invece di un'ipotesi."""
        boards = get_boards_for_country(country)
        random.shuffle(boards)  # R01 — ordine non prevedibile

        async def _query(board: dict) -> list[dict]:
            url = self.build_board_url(board, role_title, location, country)
            listings, diag = await self.extract_with_diagnostics(
                url, company_name="", source_board=board["name"]
            )
            for item in listings:
                if not item.get("company_name"):
                    item["company_name"] = "N/D"
            logger.info(
                "%s → %d annunci (status=%s, %d byte)",
                board["name"], len(listings), diag.get("status"), diag.get("bytes", 0),
            )
            if on_board_result:
                on_board_result(board["name"], diag)
            return listings

        results = await asyncio.gather(
            *(_query(b) for b in boards), return_exceptions=True
        )

        all_listings: list[dict] = []
        for board, result in zip(boards, results):
            if isinstance(result, asyncio.CancelledError):
                raise result
            if isinstance(result, BaseException):
                # un portale che esplode non deve far fallire tutta la ricerca
                logger.warning("Board %s fallito: %s", board["name"], result)
                if on_board_result:
                    on_board_result(
                        board["name"],
                        {"outcome": "error", "error": str(result), "listings": 0},
                    )
                continue
            all_listings.extend(result)

        return all_listings

    async def scrape_company_careers(
        self, company_name: str, careers_url: str
    ) -> list[dict]:
        return await self.extract_listings_from_page(
            careers_url, company_name=company_name, source_board="careers_page"
        )
