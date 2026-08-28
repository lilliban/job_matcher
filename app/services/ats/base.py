"""
Connettori ATS — contratto comune.

Perché esistono (vedi ADR-017): lo scraping HTML passa ogni pagina all'LLM
per estrarne gli annunci (ADR-008). È la scelta giusta per HTML arbitrario,
ma è sprecata quando l'azienda pubblica già gli stessi dati in JSON
strutturato. Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee
e Personio espongono tutti un feed pubblico senza autenticazione — sono
pensati per essere indicizzati dai motori di ricerca.

Il guadagno non è solo di velocità: i campi che servono a filtrare (tipo di
contratto, sede, remoto/ibrido, seniority, data di pubblicazione) arrivano
già separati, invece di essere indovinati da un modello a partire dal testo.

Contratto di `fetch`:
    None  → l'azienda non sta su questo ATS (404): si prova il prossimo
    []    → ci sta, ma non ha posizioni aperte in questo momento
    [...] → annunci, già nel formato che search_runner._process_listings
            si aspetta
"""
import html as html_module
import logging
import re
from abc import ABC, abstractmethod

import httpx

from app.core.config import SCRAPER_TIMEOUT

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def clean_html(raw: str | None) -> str:
    """Da HTML (anche doppiamente escapato, come lo restituisce Greenhouse)
    a testo leggibile. Volutamente senza BeautifulSoup: qui l'input è un
    campo di un JSON, non una pagina intera da navigare, e una regex è
    abbondantemente sufficiente."""
    if not raw:
        return ""
    text = html_module.unescape(raw)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(p|div|li|h[1-6])>", "\n", text, flags=re.I)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.I)
    text = _TAG_RE.sub("", text)
    text = html_module.unescape(text)
    return _WS_RE.sub("\n\n", text).strip()


def first_nonempty(*values) -> str | None:
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


class ATSConnector(ABC):
    """Un provider ATS. Le sottoclassi implementano solo `fetch`."""

    #: nome del provider, usato come CompanyProfile.ats_provider
    name: str = ""

    def __init__(self, timeout: float = SCRAPER_TIMEOUT):
        self.timeout = timeout

    async def _get(self, url: str) -> tuple[int, object | None, str]:
        """Ritorna (status, json_decodificato_o_None, testo_grezzo)."""
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as c:
            resp = await c.get(
                url,
                headers={
                    "User-Agent": "JobMatcher/1.0 (+ricerca lavoro personale)",
                    "Accept": "application/json, text/xml;q=0.9, */*;q=0.5",
                },
            )
        if resp.status_code != 200:
            return resp.status_code, None, resp.text
        try:
            return resp.status_code, resp.json(), resp.text
        except ValueError:
            return resp.status_code, None, resp.text

    @abstractmethod
    async def fetch(self, slug: str) -> list[dict] | None:
        """None = azienda non presente su questo ATS. Vedi il modulo."""

    # -----------------------------------------------------------------
    def _listing(
        self,
        *,
        title: str,
        url: str | None,
        description: str = "",
        requirements: str = "",
        location: str | None = None,
        contract_type: str | None = None,
        posted_date: str | None = None,
        work_mode: str | None = None,
        seniority: str | None = None,
        department: str | None = None,
    ) -> dict:
        """Formato unico verso search_runner.

        Le chiavi title/description/requirements_raw/location/contract_type/
        posted_date sono quelle che _process_listings già legge. Le altre
        (work_mode, seniority, department) arrivano gratis dal JSON dell'ATS
        e vengono conservate per i filtri strutturati."""
        return {
            "title": title.strip(),
            "source_url": url,
            "description": description,
            "requirements_raw": requirements or description,
            "location": location,
            "contract_type": contract_type,
            "posted_date": posted_date,
            "work_mode": work_mode,
            "seniority": seniority,
            "department": department,
            "source_kind": "ats",
        }
