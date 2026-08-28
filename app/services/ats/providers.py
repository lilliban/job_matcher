"""
Implementazioni per singolo ATS.

Tutti in un file perché ciascun connettore è una ventina di righe e la
differenza tra loro è solo la forma del JSON — sette file quasi vuoti
renderebbero più difficile confrontarli, non più facile.

Nota sulla rilevazione: un 404 significa "questa azienda non sta qui" ed è
un segnale pulito (Greenhouse, Lever, Ashby, Recruitee, Personio). Altri
provider (SmartRecruiters, Workable) rispondono 200 anche per uno slug
inesistente, con una lista vuota: lì "non trovata" e "nessuna posizione
aperta" sono indistinguibili, e la discovery lo tiene in conto.
"""
import logging
from xml.etree import ElementTree

from app.core.config import SCRAPER_MAX_LISTINGS_PER_SOURCE
from app.services.ats.base import ATSConnector, clean_html, first_nonempty

logger = logging.getLogger(__name__)


class GreenhouseConnector(ATSConnector):
    name = "greenhouse"

    async def fetch(self, slug: str) -> list[dict] | None:
        status, data, _ = await self._get(
            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        )
        if status == 404 or not isinstance(data, dict):
            return None
        out = []
        for j in data.get("jobs", []):
            body = clean_html(j.get("content"))
            # "Time Type: Full time" sta nei metadata, non in un campo suo
            contract = next(
                (m.get("value") for m in (j.get("metadata") or [])
                 if str(m.get("name", "")).lower() in ("time type", "employment type")
                 and m.get("value")),
                None,
            )
            out.append(self._listing(
                title=j.get("title") or "",
                url=j.get("absolute_url"),
                description=body[:2000],
                requirements=body,
                location=(j.get("location") or {}).get("name"),
                contract_type=contract,
                posted_date=first_nonempty(j.get("first_published"), j.get("updated_at")),
                department=next(
                    (d.get("name") for d in (j.get("departments") or []) if d.get("name")),
                    None,
                ),
            ))
        return out


class LeverConnector(ATSConnector):
    name = "lever"

    async def fetch(self, slug: str) -> list[dict] | None:
        status, data, _ = await self._get(
            f"https://api.lever.co/v0/postings/{slug}?mode=json"
        )
        if status == 404 or not isinstance(data, list):
            return None
        out = []
        for j in data:
            cats = j.get("categories") or {}
            body = j.get("descriptionPlain") or clean_html(j.get("description"))
            extra = "\n\n".join(
                clean_html(s.get("text")) for s in (j.get("lists") or []) if s.get("text")
            )
            full = f"{body}\n\n{extra}".strip()
            out.append(self._listing(
                title=j.get("text") or "",
                url=j.get("hostedUrl") or j.get("applyUrl"),
                description=body[:2000],
                requirements=full,
                location=cats.get("location"),
                contract_type=cats.get("commitment"),
                posted_date=j.get("createdAt"),
                work_mode=(j.get("workplaceType") or None),
                department=cats.get("team") or cats.get("department"),
            ))
        return out


class AshbyConnector(ATSConnector):
    name = "ashby"

    async def fetch(self, slug: str) -> list[dict] | None:
        status, data, _ = await self._get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        )
        if status == 404 or not isinstance(data, dict):
            return None
        out = []
        for j in data.get("jobs", []):
            if j.get("isListed") is False:
                continue
            body = j.get("descriptionPlain") or clean_html(j.get("descriptionHtml"))
            mode = j.get("workplaceType")
            if not mode and j.get("isRemote"):
                mode = "Remote"
            out.append(self._listing(
                title=j.get("title") or "",
                url=j.get("jobUrl") or j.get("applyUrl"),
                description=body[:2000],
                requirements=body,
                location=j.get("location"),
                contract_type=j.get("employmentType"),
                posted_date=j.get("publishedAt"),
                work_mode=mode,
                department=first_nonempty(j.get("department"), j.get("team")),
            ))
        return out


class RecruiteeConnector(ATSConnector):
    name = "recruitee"

    async def fetch(self, slug: str) -> list[dict] | None:
        status, data, _ = await self._get(f"https://{slug}.recruitee.com/api/offers/")
        if status == 404 or not isinstance(data, dict):
            return None
        out = []
        for j in data.get("offers", []):
            body = clean_html(j.get("description")) + "\n\n" + clean_html(j.get("requirements"))
            city = first_nonempty(j.get("city"), j.get("location"))
            country = j.get("country")
            out.append(self._listing(
                title=j.get("title") or "",
                url=j.get("careers_url") or j.get("careers_apply_url"),
                description=clean_html(j.get("description"))[:2000],
                requirements=body.strip(),
                location=", ".join(x for x in (city, country) if x) or None,
                contract_type=j.get("employment_type_code") or j.get("category_code"),
                posted_date=j.get("published_at") or j.get("created_at"),
                work_mode=j.get("remote_option") or None,
                department=j.get("department"),
            ))
        return out


class PersonioConnector(ATSConnector):
    name = "personio"

    async def fetch(self, slug: str) -> list[dict] | None:
        # Personio pubblica XML, non JSON — molto usato in Germania.
        status, _, text = await self._get(f"https://{slug}.jobs.personio.de/xml")
        if status == 404:
            return None
        # Uno slug inesistente NON dà 404: redirige a www.personio.com e
        # restituisce 200 con la loro pagina di marketing. Senza questo
        # controllo il connettore direbbe "sì, è qui" per ogni azienda.
        if "<workzag-jobs" not in text[:1000]:
            return None
        try:
            root = ElementTree.fromstring(text)
        except ElementTree.ParseError as exc:
            logger.info("Personio %s: XML non valido (%s)", slug, exc)
            return None

        out = []
        for pos in root.findall(".//position"):
            def _t(tag: str) -> str | None:
                el = pos.find(tag)
                return el.text.strip() if el is not None and el.text else None

            # struttura reale: jobDescriptions > jobDescription > name|value
            body = "\n\n".join(
                f"{d.findtext('name') or ''}\n{clean_html(d.findtext('value') or '')}".strip()
                for d in pos.findall("./jobDescriptions/jobDescription")
            ).strip()
            pid = _t("id")
            out.append(self._listing(
                title=_t("name") or "",
                url=f"https://{slug}.jobs.personio.de/job/{pid}" if pid else None,
                description=body[:2000],
                requirements=body,
                location=first_nonempty(_t("office"), _t("city")),
                contract_type=first_nonempty(_t("employmentType"), _t("schedule")),
                posted_date=_t("createdAt"),
                # Personio è l'unico che dichiara gli anni di esperienza
                # come campo strutturato (es. "7-10") invece che nel testo
                seniority=first_nonempty(_t("seniority"), _t("yearsOfExperience")),
                department=first_nonempty(_t("department"), _t("recruitingCategory")),
            ))
        return out


class SmartRecruitersConnector(ATSConnector):
    name = "smartrecruiters"

    async def fetch(self, slug: str) -> list[dict] | None:
        status, data, _ = await self._get(
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100"
        )
        if status == 404 or not isinstance(data, dict):
            return None
        postings = data.get("content") or []
        if not postings:
            # 200 con lista vuota: slug sbagliato o davvero nessuna
            # posizione aperta — indistinguibili da qui
            return []

        out = []
        for j in postings[:SCRAPER_MAX_LISTINGS_PER_SOURCE]:
            loc = j.get("location") or {}
            mode = "Remote" if loc.get("remote") else ("Hybrid" if loc.get("hybrid") else None)
            # la lista non contiene il testo dell'annuncio: serve il dettaglio
            body = await self._detail_text(slug, j.get("id"))
            out.append(self._listing(
                title=j.get("name") or "",
                url=f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
                description=body[:2000],
                requirements=body,
                location=", ".join(
                    x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x
                ) or None,
                contract_type=(j.get("typeOfEmployment") or {}).get("label"),
                posted_date=j.get("releasedDate"),
                work_mode=mode,
                seniority=(j.get("experienceLevel") or {}).get("label"),
                department=(j.get("department") or {}).get("label"),
            ))
        return out

    async def _detail_text(self, slug: str, posting_id: str | None) -> str:
        if not posting_id:
            return ""
        status, data, _ = await self._get(
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{posting_id}"
        )
        if status != 200 or not isinstance(data, dict):
            return ""
        sections = ((data.get("jobAd") or {}).get("sections")) or {}
        parts = [
            clean_html((sections.get(k) or {}).get("text"))
            for k in ("jobDescription", "qualifications", "additionalInformation")
        ]
        return "\n\n".join(p for p in parts if p).strip()


class WorkableConnector(ATSConnector):
    name = "workable"

    async def fetch(self, slug: str) -> list[dict] | None:
        status, data, _ = await self._get(
            f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
        )
        if status == 404 or not isinstance(data, dict):
            return None
        out = []
        for j in data.get("jobs", []):
            body = clean_html(j.get("description")) + "\n\n" + clean_html(j.get("requirements"))
            out.append(self._listing(
                title=j.get("title") or "",
                url=j.get("url") or j.get("application_url"),
                description=clean_html(j.get("description"))[:2000],
                requirements=body.strip(),
                location=first_nonempty(
                    j.get("location"),
                    ", ".join(x for x in (j.get("city"), j.get("country")) if x) or None,
                ),
                contract_type=j.get("employment_type"),
                posted_date=j.get("published_on") or j.get("created_at"),
                work_mode="Remote" if j.get("telecommuting") else None,
                department=j.get("department"),
            ))
        return out


# L'ordine conta: la discovery prova i provider in sequenza e si ferma al
# primo che risponde. Davanti quelli che danno un 404 pulito su slug
# sbagliato; poi quelli che rispondono 200 con lista vuota, dove "non è qui"
# e "nessuna posizione aperta" sono indistinguibili; ultimo Personio, il cui
# caso negativo costa 1,7 MB di HTML scaricato prima di poterlo escludere.
ALL_CONNECTORS: list[type[ATSConnector]] = [
    GreenhouseConnector,
    LeverConnector,
    AshbyConnector,
    RecruiteeConnector,
    SmartRecruitersConnector,
    WorkableConnector,
    PersonioConnector,
]

BY_NAME: dict[str, type[ATSConnector]] = {c.name: c for c in ALL_CONNECTORS}
