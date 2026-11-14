"""
Catalogo aziende — navigazione per ambito e settore.

L'utente non sa il nome delle aziende da cercare: sa che vuole "una
multinazionale farmaceutica" o "una PMI tech italiana". Qui si traduce
questa scelta a due livelli (ambito → settore) in una richiesta al motore
di scoperta, che poi verifica che le aziende esistano.
"""
from app.services import geo
from app.services.company_discovery import CompanyDiscoveryEngine

SCOPES: list[dict] = [
    {"key": "national", "label": "Nazionali", "hint": "Aziende del tuo paese",
     "needs_country": True,
     "query": "aziende con sede principale in {country}, di dimensioni medio-grandi"},
    {"key": "europe", "label": "Europee", "hint": "Grandi aziende con base in Europa",
     "needs_country": False,
     "query": "grandi aziende europee con sede in Europa"},
    {"key": "multinational", "label": "Multinazionali", "hint": "Gruppi globali presenti in molti paesi",
     "needs_country": False,
     "query": "multinazionali globali presenti in molti paesi"},
    {"key": "sme", "label": "PMI", "hint": "Piccole e medie imprese",
     "needs_country": True,
     "query": "piccole e medie imprese (PMI) con sede in {country}"},
    {"key": "startup", "label": "Startup", "hint": "Startup e scale-up in crescita",
     "needs_country": False,
     "query": "startup e scale-up innovative in forte crescita in Europa"},
]

SECTORS: list[dict] = [
    {"key": "tech", "label": "Tech e software", "query": "tecnologia, software e servizi IT"},
    {"key": "pharma", "label": "Farmaceutico e biotech", "query": "farmaceutico, biotecnologie e life sciences"},
    {"key": "healthcare", "label": "Sanità e medicale", "query": "sanità, dispositivi medici e servizi sanitari"},
    {"key": "consulting", "label": "Consulenza", "query": "consulenza strategica, di management e IT"},
    {"key": "finance", "label": "Finanza e assicurazioni", "query": "banche, assicurazioni e servizi finanziari"},
    {"key": "manufacturing", "label": "Manifattura e industria", "query": "manifattura e industria"},
    {"key": "automotive", "label": "Automotive", "query": "automotive e mobilità"},
    {"key": "energy", "label": "Energia e utility", "query": "energia, utility e rinnovabili"},
    {"key": "telecom", "label": "Telecomunicazioni", "query": "telecomunicazioni e media"},
    {"key": "retail", "label": "Retail e moda", "query": "retail, moda e beni di consumo"},
    {"key": "food", "label": "Food & beverage", "query": "alimentare e beverage"},
    {"key": "logistics", "label": "Logistica e trasporti", "query": "logistica, trasporti e supply chain"},
]

_SCOPE = {s["key"]: s for s in SCOPES}
_SECTOR = {s["key"]: s for s in SECTORS}


def catalog() -> dict:
    return {
        "scopes": [{k: v for k, v in s.items() if k != "query"} for s in SCOPES],
        "sectors": [{"key": s["key"], "label": s["label"]} for s in SECTORS],
        "countries": [{"code": c["code"], "name": c["name"]} for c in geo.countries()],
    }


async def browse(
    engine: CompanyDiscoveryEngine,
    scope: str,
    sector: str,
    country_code: str | None = None,
    exclude: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Aziende dell'ambito e settore scelti, escluse quelle già mostrate
    (così "mostrane altre" non ripropone le stesse)."""
    sc = _SCOPE.get(scope)
    se = _SECTOR.get(sector)
    if not sc or not se:
        raise ValueError("Ambito o settore non valido")

    country_name = geo.display_name(country_code) if country_code else None
    if sc["needs_country"] and not country_name:
        raise ValueError("Per questo ambito serve scegliere un paese")

    query = f"{sc['query'].format(country=country_name or '')} nel settore {se['query']}"
    skip = {n.lower().strip() for n in (exclude or [])}
    if skip:
        query += f". Escludi queste: {', '.join(sorted(skip)[:40])}"

    # si chiede qualcosa in più del necessario: parte verrà scartata perché
    # già mostrata o perché non verificata
    found = await engine.search_companies(
        query, sector=se["label"], limit=limit + len(skip) // 2 + 4,
        country_code=country_code if sc["needs_country"] else None,
    )
    out = [
        c for c in found
        if c["name"].lower().strip() not in skip and c.get("exists_online", True)
    ]
    return out[:limit]
