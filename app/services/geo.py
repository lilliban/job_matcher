"""
Geografia della ricerca: continente > stato > regione.

Il dataset è un JSON versionato in `app/data/geo.json`, non una dipendenza
pip e non una tabella: `pycountry` non ha né regioni utili né coordinate,
`geonames` richiede un download enorme o una registrazione, ed entrambi
contraddicono il "zero setup" di ADR-001.

**A cosa serve davvero questa gerarchia.** Non a filtrare gli annunci dopo
averli raccolti: serve a costruire l'URL di ricerca giusto per ogni
portale. È il motivo per cui non c'è nessun raggio in chilometri — il campo
"sede" degli annunci è testo libero, spesso assente, e un raggio calcolato
su quello prometterebbe una precisione che non ha.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_GEO_PATH = Path(__file__).resolve().parent.parent / "data" / "geo.json"


@lru_cache(maxsize=1)
def _data() -> dict:
    try:
        with _GEO_PATH.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("geo.json non leggibile (%s) — geografia disabilitata", exc)
        return {"continents": [], "countries": []}


@lru_cache(maxsize=1)
def _by_code() -> dict[str, dict]:
    return {c["code"]: c for c in _data().get("countries", [])}


def countries() -> list[dict]:
    return _data().get("countries", [])


def continents() -> list[dict]:
    return _data().get("continents", [])


def is_continent(code: str | None) -> bool:
    if not code:
        return False
    return any(c["code"] == code.upper() for c in continents())


def regions_for(code: str | None) -> list[str]:
    """Regioni di uno stato. Vuoto per un continente: è il segnale con cui
    la UI disabilita il campo Zona invece di accettare testo che verrebbe
    poi ignorato."""
    if not code or is_continent(code):
        return []
    entry = _by_code().get(code.upper())
    return list(entry.get("regions", [])) if entry else []


def search_name(code: str | None) -> str | None:
    """Nome da mandare ai portali globali — in inglese, vedi ADR-019."""
    if not code:
        return None
    code = code.upper()
    if is_continent(code):
        return next(
            (c.get("search_name", c["name"]) for c in continents() if c["code"] == code),
            None,
        )
    entry = _by_code().get(code)
    return entry.get("search_name") if entry else None


def display_name(code: str | None) -> str | None:
    """Nome da mostrare all'utente — in italiano."""
    if not code:
        return None
    code = code.upper()
    entry = _by_code().get(code)
    if entry:
        return entry["name"]
    return next((c["name"] for c in continents() if c["code"] == code), None)


def countries_of(continent_code: str) -> list[str]:
    return next(
        (c.get("countries", []) for c in continents()
         if c["code"] == continent_code.upper()),
        [],
    )


def is_valid_region(country_code: str | None, region: str | None) -> bool:
    """Una zona vale solo dentro il suo stato. Impedisce che "Marche" resti
    incollata alla ricerca dopo aver cambiato Paese in Germania."""
    if not region:
        return True
    return region in regions_for(country_code)


def tree() -> dict:
    """Struttura che il frontend usa per popolare i due menu a tendina."""
    return {
        "continents": [
            {"code": c["code"], "name": c["name"], "countries": c.get("countries", [])}
            for c in continents()
        ],
        "countries": [
            {"code": c["code"], "name": c["name"], "regions": c.get("regions", [])}
            for c in countries()
        ],
    }
