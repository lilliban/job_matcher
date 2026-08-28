"""
Discovery: su quale ATS pubblica un'azienda, e con che slug.

È la parte difficile del meccanismo. Nessun ATS espone un indice "dammi
tutte le aziende che usano il mio servizio", quindi l'unico modo è provare:
si costruiscono alcuni slug plausibili dal nome e dal dominio, e si
interrogano i provider finché uno risponde.

Il costo si paga UNA VOLTA per azienda. L'esito — positivo o negativo —
viene scritto su CompanyProfile, quindi la ricerca successiva sulla stessa
azienda non prova più niente: o va dritta al connettore giusto, o sa già di
dover usare lo scraping HTML.

Ricordare i fallimenti è importante quanto ricordare i successi: senza,
ogni ricerca ripagherebbe l'intero giro di tentativi per le (molte) aziende
che un ATS pubblico non ce l'hanno.
"""
import asyncio
import logging
import re
import unicodedata
from urllib.parse import urlparse

from app.services.ats.providers import ALL_CONNECTORS, BY_NAME

logger = logging.getLogger(__name__)

# suffissi societari che non fanno parte dello slug su nessun ATS
_LEGAL_SUFFIXES = {
    "srl", "s.r.l", "spa", "s.p.a", "srls", "snc", "sas", "sl", "sa",
    "gmbh", "ag", "kg", "ug", "bv", "nv", "ltd", "limited", "llc", "inc",
    "incorporated", "corp", "corporation", "co", "plc", "oy", "ab", "as",
    "aps", "sarl", "sas", "se", "holding", "group", "groupe", "gruppo",
}

# quanti slug diversi provare al massimo per azienda: oltre, il costo del
# tentativo supera il beneficio di trovare un ATS per un'azienda con un nome
# molto diverso dal proprio dominio
MAX_SLUG_CANDIDATES = 3


def name_key(name: str) -> str:
    """Chiave di identità di un'azienda: minuscolo, accenti via, spazi
    compattati. Serve a riconoscere 'Ferrari S.p.A.' e 'ferrari  spa' come
    la stessa azienda quando si cerca nel registro."""
    norm = unicodedata.normalize("NFKD", name or "")
    ascii_only = norm.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_only).strip().lower()


def _tokens(name: str) -> list[str]:
    """Token dello slug. Si scartano i suffissi societari e i token di un
    solo carattere: "Ferrari S.p.A." va normalizzato a `ferrari`, non a
    `ferrari-s-p-a` — la punteggiatura di "S.p.A." si sbriciola in tre
    lettere isolate che non compaiono in nessuno slug reale."""
    raw = re.split(r"[^a-z0-9]+", name_key(name))
    return [t for t in raw if len(t) > 1 and t not in _LEGAL_SUFFIXES]


def slug_candidates(name: str, website: str | None = None) -> list[str]:
    """Slug plausibili, dal più probabile al meno.

    Il dominio viene per primo quando c'è: un'azienda che si chiama
    "Datadog" ma sta su `datadoghq.com` può avere lo slug in entrambe le
    forme, e il dominio è il segnale più forte su chi sia davvero."""
    candidates: list[str] = []

    if website:
        host = urlparse(website if "//" in website else f"https://{website}").netloc
        host = host.lower().removeprefix("www.")
        label = host.split(".")[0] if host else ""
        if label and label not in ("careers", "jobs", "work"):
            candidates.append(label)

    toks = _tokens(name)
    if toks:
        candidates.append("".join(toks))
        if len(toks) > 1:
            candidates.append("-".join(toks))

    seen: set[str] = set()
    out = []
    for c in candidates:
        c = re.sub(r"[^a-z0-9-]", "", c)
        if c and len(c) >= 2 and c not in seen:
            seen.add(c)
            out.append(c)
    return out[:MAX_SLUG_CANDIDATES]


async def discover(name: str, website: str | None = None) -> dict | None:
    """Prova i provider per ogni slug candidato.

    Ritorna {"provider", "slug", "listings"} al primo esito utile, oppure
    None se nessun ATS conosce questa azienda.

    Uno slug per volta, ma tutti i provider in parallelo: i provider stanno
    su host diversi, quindi la concorrenza non concentra traffico su
    nessuno. Si esce al primo provider che restituisce annunci."""
    for slug in slug_candidates(name, website):
        async def _try(cls, slug=slug):
            try:
                listings = await cls().fetch(slug)
            except Exception as exc:  # noqa: BLE001
                logger.debug("ATS %s/%s fallito: %s", cls.name, slug, exc)
                return None
            if listings:  # lista vuota = ambiguo, non lo consideriamo un match
                return {"provider": cls.name, "slug": slug, "listings": listings}
            return None

        results = await asyncio.gather(
            *(_try(c) for c in ALL_CONNECTORS), return_exceptions=True
        )
        # ALL_CONNECTORS è ordinato per affidabilità del segnale: si tiene
        # il primo che ha risposto, non uno a caso
        for r in results:
            if isinstance(r, dict):
                logger.info(
                    "ATS trovato per '%s': %s/%s (%d annunci)",
                    name, r["provider"], r["slug"], len(r["listings"]),
                )
                return r
    return None


async def fetch_known(provider: str, slug: str) -> list[dict] | None:
    """Percorso veloce per un'azienda il cui ATS è già noto: una sola
    richiesta JSON, nessuna chiamata LLM, nessun tentativo."""
    cls = BY_NAME.get(provider)
    if not cls:
        logger.warning("Provider ATS sconosciuto: %s", provider)
        return None
    try:
        return await cls().fetch(slug)
    except Exception as exc:  # noqa: BLE001
        logger.info("Fetch ATS %s/%s fallito: %s", provider, slug, exc)
        return None
