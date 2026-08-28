"""
Logica delle collezioni di aziende.

Il problema che risolve rispetto a `suggest_similar` (ADR-005): quel
meccanismo passa all'LLM la lista completa delle aziende scelte, e ADR-005
dichiara esplicitamente che il prompt cresce senza troncamento. Con cinque
aziende va benissimo; con cinquanta il prompt diventa lungo e costoso, e
per giunta ripete a ogni richiesta un'informazione che non cambia.

Qui la collezione viene prima riassunta in una frase ("PMI manifatturiere
del Centro Italia, 50-200 dipendenti"), il riassunto viene salvato, e le
richieste successive usano quello più un campione di nomi. Il riassunto si
rigenera solo quando la collezione cambia dimensione in modo significativo.
"""
import logging

from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)

# Quante aziende si citano per nome quando si chiedono simili. Oltre questa
# soglia si usa il riassunto: elencarne cinquanta non rende il suggerimento
# più mirato, allunga solo il prompt.
SAMPLE_SIZE = 15

# Di quante aziende deve cambiare una collezione perché valga la pena
# rigenerare il riassunto invece di riusare quello salvato.
RESUMMARIZE_DELTA = 5

COMPANY_THEMES: dict[str, dict] = {
    "tech": {"label": "Aziende tech", "query": "aziende tecnologiche e software"},
    "sport": {"label": "Sport", "query": "aziende del settore sportivo e articoli sportivi"},
    "luxury": {"label": "Brand di lusso", "query": "brand di moda e lusso"},
    "manufacturing": {"label": "Manifatturiero", "query": "aziende manifatturiere e industriali"},
    "finance": {"label": "Finanza", "query": "banche, assicurazioni e servizi finanziari"},
    "health": {"label": "Salute", "query": "aziende del settore sanitario e biomedicale"},
    "food": {"label": "Food & beverage", "query": "aziende alimentari e del beverage"},
    "energy": {"label": "Energia", "query": "aziende del settore energetico e rinnovabili"},
    "consulting": {"label": "Consulenza", "query": "società di consulenza"},
    "startup": {"label": "Startup", "query": "startup innovative e scale-up"},
}


def member_names(coll: models.CompanyCollection) -> list[str]:
    return [m.name for m in coll.members]


async def collection_profile(
    db: Session, coll: models.CompanyCollection, engine
) -> str | None:
    """Riassume il carattere della collezione, e lo salva.

    Si rigenera solo se la collezione è cresciuta o calata di almeno
    RESUMMARIZE_DELTA aziende: il riassunto di 20 aziende e quello di 22 è
    lo stesso, e rifarlo costerebbe una chiamata per niente."""
    names = member_names(coll)
    if len(names) < 3:
        return None  # con due aziende non c'è un "carattere" da riassumere

    stale = abs(len(names) - (coll.profile_summary_size or 0)) >= RESUMMARIZE_DELTA
    if coll.profile_summary and not stale:
        return coll.profile_summary

    prompt = (
        "Queste aziende fanno parte della stessa collezione di un utente "
        f"che cerca lavoro: {', '.join(names[:40])}.\n\n"
        "Descrivi in UNA frase cosa hanno in comune: settore, dimensione "
        "tipica, area geografica, tipo di cultura aziendale. "
        "Rispondi solo con la frase, in italiano."
    )
    try:
        summary = await engine.llm.complete(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.info("Riassunto collezione non riuscito: %s", exc)
        return coll.profile_summary

    if summary:
        coll.profile_summary = summary.strip()[:600]
        coll.profile_summary_size = len(names)
        db.commit()
    return coll.profile_summary


async def suggest_for_collection(
    db: Session,
    coll: models.CompanyCollection,
    engine,
    limit: int = 8,
    country_code: str | None = None,
) -> list[dict]:
    """Aziende simili alla collezione nel suo insieme.

    Sotto SAMPLE_SIZE aziende si passa la lista intera, che è il
    comportamento di ADR-005 e funziona bene. Sopra, si passa il riassunto
    più un campione: il costo smette di crescere con la collezione."""
    names = member_names(coll)
    if not names:
        return []

    if len(names) <= SAMPLE_SIZE:
        return await engine.suggest_similar(
            names, sector=coll.description or None,
            limit=limit, country_code=country_code,
        )

    summary = await collection_profile(db, coll, engine)
    # campione stabile: le prime e le ultime aggiunte, così il suggerimento
    # non salta da un giro all'altro senza che l'utente abbia toccato nulla
    sample = names[:SAMPLE_SIZE // 2] + names[-(SAMPLE_SIZE // 2):]
    return await engine.suggest_similar(
        sample,
        sector=(summary or coll.description or None),
        limit=limit,
        country_code=country_code,
    )


async def companies_by_theme(
    engine, theme_key: str, location: str | None = None,
    limit: int = 8, country_code: str | None = None,
) -> list[dict]:
    """Aziende di un tema ("brand di lusso"). Passa dalla stessa verifica
    anti-invenzione delle altre ricerche (ADR-006)."""
    theme = COMPANY_THEMES.get(theme_key)
    query = theme["query"] if theme else theme_key
    return await engine.search_companies(
        query, location=location, limit=limit, country_code=country_code
    )


def apply_to_session(
    db: Session, coll: models.CompanyCollection, user_id: str, session_id: str
) -> int:
    """Copia i membri della collezione tra le aziende target di una ricerca.

    Copia e non riferimento: una ricerca conclusa deve restare leggibile
    così com'era, anche se mesi dopo la collezione da cui era partita viene
    svuotata. Le aziende già presenti nella ricerca vengono saltate senza
    farne un errore."""
    session = db.get(models.SearchSession, session_id)
    if not session or session.user_id != user_id:
        return 0

    existing = {c.name.lower().strip() for c in session.companies}
    added = 0
    for m in coll.members:
        if m.name.lower().strip() in existing:
            continue
        db.add(models.TargetCompany(
            session_id=session.id, name=m.name, country=m.country,
            size=m.size, sector=m.sector, website=m.website,
            source=f"collection:{coll.name}"[:60],
        ))
        existing.add(m.name.lower().strip())
        added += 1
    db.commit()
    return added
