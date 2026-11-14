"""
ApplicationBuilder — candidatura "al volo" da un link.

Differenza rispetto al flusso delle ricerche: qui non c'è una sessione né
un match. L'utente incolla l'URL di UN annuncio (o ne incolla il testo),
aggiunge linee guida/schema (testo e/o file) e ottiene CV e lettera scritti
secondo quello schema. Niente viene salvato in DB.

Tre compiti:
  1. fetch_listing      — URL → annuncio strutturato (stesso pattern dello
                          scraper: testo grezzo + LLM, nessun selettore CSS)
  2. extract_file_text  — file di linee guida (PDF/DOCX/TXT/MD) → testo
  3. build_user_profile — User ORM → dict per DocumentGenerator
"""
import io
import logging
from urllib.parse import urlparse

from app.models import User
from app.services.cv_parser import CVParser
from app.services.llm_gateway import LLMGateway
from app.services.scraper import MAX_PAGE_CHARS, ScraperEngine

logger = logging.getLogger(__name__)

MAX_GUIDELINE_FILE_SIZE = 5 * 1024 * 1024
TEXT_EXTENSIONS = (".txt", ".md", ".markdown")


class ApplicationBuilderError(Exception):
    """Errore atteso, con messaggio leggibile dall'utente."""


def build_user_profile(user: User) -> dict:
    return {
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "location": user.location,
        "bio": user.bio,
        "soft_skills": [s.name for s in user.soft_skills],
        "hard_skills": [
            {"name": s.name, "level": s.level, "years_exp": s.years_exp,
             "acquired_via": s.acquired_via}
            for s in user.hard_skills
        ],
        "experiences": [
            {"company": e.company, "role": e.role, "start_date": e.start_date,
             "end_date": e.end_date, "description": e.description,
             "skills_used": e.skills_used}
            for e in user.experiences
        ],
        "education": [
            {"institution": e.institution, "degree": e.degree,
             "field": e.field, "year": e.year}
            for e in user.education
        ],
        "base_documents": {
            d.doc_type: d.content for d in user.base_documents if d.content
        },
    }


def extract_file_text(filename: str, content: bytes) -> str:
    """Testo di un file di linee guida. Solleva ApplicationBuilderError se
    il formato non è supportato o il file non contiene testo."""
    name = (filename or "").lower()
    if len(content) > MAX_GUIDELINE_FILE_SIZE:
        raise ApplicationBuilderError(f"{filename}: file troppo grande (max 5MB)")

    try:
        if name.endswith(".pdf"):
            text = CVParser.extract_text(content)
        elif name.endswith(".docx"):
            text = _docx_text(content)
        elif name.endswith(TEXT_EXTENSIONS):
            text = content.decode("utf-8", errors="replace")
        else:
            raise ApplicationBuilderError(
                f"{filename}: formato non supportato (usa PDF, DOCX, TXT o MD)"
            )
    except ApplicationBuilderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ApplicationBuilderError(f"{filename}: impossibile leggerlo ({exc})") from exc

    text = text.strip()
    if not text:
        raise ApplicationBuilderError(
            f"{filename}: nessun testo estraibile (forse è una scansione)"
        )
    return text


def _docx_text(content: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(content))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


class ApplicationBuilder:
    def __init__(self, llm: LLMGateway):
        self.llm = llm
        self.scraper = ScraperEngine(llm)

    async def fetch_listing(self, url: str | None, job_text: str | None) -> dict:
        """Annuncio strutturato da URL oppure da testo incollato.

        Il testo incollato ha la precedenza: è il ripiego per le pagine che
        non si lasciano scaricare (login, anti-bot, shell JavaScript)."""
        raw = (job_text or "").strip()
        source_url = None

        if not raw:
            if not url:
                raise ApplicationBuilderError("Serve il link dell'annuncio o il suo testo")
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ApplicationBuilderError("Il link deve iniziare con http:// o https://")

            html, diag = await self.scraper._fetch(url)
            if html is None:
                raise ApplicationBuilderError(
                    f"Impossibile scaricare la pagina ({diag.get('error') or diag.get('status')}). "
                    "Incolla il testo dell'annuncio nel campo apposito."
                )
            raw = self.scraper._strip_html(html, url)
            source_url = url

            marker = self.scraper._blocked_page_marker(raw)
            if marker:
                raise ApplicationBuilderError(
                    "Il sito ha bloccato la lettura automatica. "
                    "Incolla il testo dell'annuncio nel campo apposito."
                )
            if len(raw) < 200:
                raise ApplicationBuilderError(
                    "La pagina non contiene testo leggibile (spesso il contenuto "
                    "è caricato via JavaScript). Incolla il testo dell'annuncio."
                )

        prompt = (
            "Questo è il testo di una pagina con UN annuncio di lavoro. "
            "Estrai i dati in JSON. Usa SOLO informazioni presenti nel testo, "
            "non inventare nulla; se manca un dato usa null.\n\n"
            "Rispondi SOLO con un oggetto JSON con queste chiavi:\n"
            '  "title": titolo della posizione\n'
            '  "company_name": nome dell\'azienda che assume\n'
            '  "location": sede/modalità di lavoro\n'
            '  "requirements": TUTTO ciò che riguarda mansioni, requisiti, '
            "competenze richieste e cosa offre l'azienda, come testo fedele "
            "all'originale (non riassumere)\n\n"
            f"TESTO:\n{raw[:MAX_PAGE_CHARS]}"
        )
        data = await self.llm.complete_json(prompt, default=None)
        if not isinstance(data, dict) or not (data.get("title") or data.get("requirements")):
            raise ApplicationBuilderError(
                "Non sono riuscito a riconoscere un annuncio in quella pagina. "
                "Controlla il link o incolla il testo."
            )

        return {
            "title": data.get("title") or "Posizione",
            "company_name": data.get("company_name") or "",
            "location": data.get("location"),
            "requirements_raw": data.get("requirements") or raw[:2500],
            "source_url": source_url,
        }
