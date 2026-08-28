"""
CompanyDiscoveryEngine — RF2.2, RF2.3

Pipeline a tre livelli decisa in fase di design:
  1. LLM        — suggerisce nomi di aziende (anche PMI locali)
  2. Places API — verifica che l'azienda esista davvero (se configurata)
  3. Scraper    — se l'azienda non ha una careers page raggiungibile,
                  viene scartata a valle (RF3.5)

L'hallucination dell'LLM si auto-elimina: un'azienda inventata non
supera la verifica e non arriva mai all'utente.

Il meccanismo "stile Spotify" (RF2.3) passa la lista CUMULATIVA delle
aziende già selezionate, non solo l'ultima — così i suggerimenti si
affinano progressivamente.
"""
import logging

import httpx

from app.core.config import GOOGLE_PLACES_API_KEY, PLACES_TEXTSEARCH_URL
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)


class CompanyDiscoveryEngine:
    def __init__(self, llm: LLMGateway):
        self.llm = llm

    # -----------------------------------------------------------------
    # RF2.2 — ricerca aziende per ruolo / area
    # -----------------------------------------------------------------
    async def search_companies(
        self,
        query: str,
        location: str | None = None,
        sector: str | None = None,
        limit: int = 8,
        country_code: str | None = None,
    ) -> list[dict]:
        """Cerca aziende per nome libero o settore. Verifica su Places
        quando disponibile."""
        names = await self._llm_suggest_names(query, location, sector, limit)
        return await self._verify_and_enrich(names, location, source="llm", country_code=country_code)

    async def search_local_companies(
        self, sector: str, area: str, limit: int = 10,
        country_code: str | None = None,
    ) -> list[dict]:
        """RF2.2 — caso 'voglio restare a Civitanova Marche'.
        Places è la fonte migliore per le PMI locali perché l'LLM non le
        conosce. Se Places non è configurata, fallback su LLM."""
        if GOOGLE_PLACES_API_KEY:
            places = await self._places_search(f"{sector} {area}", limit=limit)
            if places:
                return places

        logger.info("Places non disponibile → fallback LLM per aziende locali")
        names = await self._llm_suggest_names(
            f"piccole e medie imprese settore {sector}", area, sector, limit
        )
        return await self._verify_and_enrich(names, area, source="llm", country_code=country_code)

    # -----------------------------------------------------------------
    # RF2.3 — suggerimenti cumulativi (effetto Spotify)
    # -----------------------------------------------------------------
    async def suggest_similar(
        self,
        selected_companies: list[str],
        location: str | None = None,
        sector: str | None = None,
        limit: int = 5,
        country_code: str | None = None,
    ) -> list[dict]:
        """Riceve la lista CUMULATIVA delle aziende già scelte.
        Più aziende sono selezionate, più il suggerimento è mirato."""
        if not selected_companies:
            return []

        selected_str = ", ".join(selected_companies)
        area_clause = f" nella zona di {location}" if location else ""
        sector_clause = f" nel settore {sector}" if sector else ""

        prompt = (
            f"L'utente ha selezionato queste aziende come target per la ricerca lavoro: "
            f"{selected_str}.\n\n"
            f"Suggerisci {limit} altre aziende REALI e simili{sector_clause}{area_clause}, "
            "per dimensione, settore e cultura aziendale. "
            "Non ripetere le aziende già selezionate.\n"
            "Includi anche piccole e medie imprese se pertinenti, non solo grandi nomi.\n\n"
            'Rispondi SOLO con un array JSON di oggetti: '
            '[{"name": "...", "sector": "...", "size": "small|medium|large", "reason": "perché è simile"}]'
        )

        data = await self.llm.complete_json(prompt, default=[])
        if not isinstance(data, list):
            return []

        already = {c.lower().strip() for c in selected_companies}
        candidates = [
            item for item in data
            if isinstance(item, dict)
            and item.get("name")
            and item["name"].lower().strip() not in already
        ]

        verified = await self._verify_and_enrich(
            [c["name"] for c in candidates], location, source="similar",
            country_code=country_code,
        )

        # riporta il campo `reason` e `sector` dal suggerimento originale
        by_name = {c["name"].lower(): c for c in candidates}
        for v in verified:
            src = by_name.get(v["name"].lower())
            if src:
                v["sector"] = v.get("sector") or src.get("sector")
                v["size"] = v.get("size") or src.get("size")
                v["reason"] = src.get("reason")
        return verified

    # -----------------------------------------------------------------
    # Interni
    # -----------------------------------------------------------------
    async def _llm_suggest_names(
        self, query: str, location: str | None, sector: str | None, limit: int
    ) -> list[dict]:
        area_clause = f" con sede o filiali nella zona di {location}" if location else ""
        sector_clause = f", settore {sector}" if sector else ""

        prompt = (
            f"Elenca {limit} aziende REALI che corrispondono a: '{query}'"
            f"{area_clause}{sector_clause}.\n"
            "Includi sia grandi aziende sia PMI locali se pertinenti.\n"
            'Rispondi SOLO con un array JSON di oggetti: '
            '[{"name": "...", "sector": "...", "size": "small|medium|large", "website": "dominio.com o null"}]'
        )
        data = await self.llm.complete_json(prompt, default=[])
        if not isinstance(data, list):
            return []
        return [d for d in data if isinstance(d, dict) and d.get("name")]

    async def _verify_and_enrich(
        self, candidates: list, location: str | None, source: str,
        country_code: str | None = None,
    ) -> list[dict]:
        """RF3.5 — verifica che le aziende esistano. Quelle inventate
        vengono marcate exists_online=False e scartate a valle."""
        out: list[dict] = []
        for item in candidates:
            name = item["name"] if isinstance(item, dict) else str(item)
            base = {
                "name": name,
                "sector": item.get("sector") if isinstance(item, dict) else None,
                "size": item.get("size") if isinstance(item, dict) else None,
                "website": item.get("website") if isinstance(item, dict) else None,
                # `location` è una ZONA ("Marche"), non un paese: scriverla
                # in `country` faceva finire una regione — o, con Places
                # attiva, un indirizzo postale intero — in un campo che
                # dovrebbe contenere un codice paese, e da lì si propagava
                # fino al profilo utente. Restava invisibile solo perché la
                # zona era quasi sempre vuota.
                "country": country_code,
                "source": source,
                "careers_url": None,
                "careers_url_verified": False,
                "exists_online": True,
            }

            if GOOGLE_PLACES_API_KEY:
                place = await self._places_lookup(name, location)
                if place:
                    base.update(place)
                    base["source"] = f"{source}+places"
                else:
                    # non trovata su Places → probabile hallucination
                    base["exists_online"] = False

            out.append(base)
        return out

    async def _places_lookup(self, name: str, location: str | None) -> dict | None:
        query = f"{name} {location or ''}".strip()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    PLACES_TEXTSEARCH_URL,
                    params={"query": query, "key": GOOGLE_PLACES_API_KEY},
                )
                resp.raise_for_status()
                data = resp.json()
            results = data.get("results") or []
            if not results:
                return None
            top = results[0]
            return {
                "name": top.get("name", name),
                # NON si scrive `country`: Places restituisce un indirizzo
                # postale completo, che in un campo "codice paese" e' la
                # terza semantica diversa nella stessa colonna.
                "address": top.get("formatted_address"),
                "exists_online": True,
            }
        except Exception as exc:  # noqa: BLE001
            logger.info("Places lookup fallito per %s: %s", name, exc)
            return None

    async def _places_search(self, query: str, limit: int = 10) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    PLACES_TEXTSEARCH_URL,
                    params={"query": query, "key": GOOGLE_PLACES_API_KEY},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.info("Places search fallita: %s", exc)
            return []

        out = []
        for r in (data.get("results") or [])[:limit]:
            out.append({
                "name": r.get("name"),
                "address": r.get("formatted_address"),
                "country": None,
                "sector": None,
                "size": None,
                "website": None,
                "source": "places",
                "careers_url": None,
                "careers_url_verified": False,
                "exists_online": True,
            })
        return out
