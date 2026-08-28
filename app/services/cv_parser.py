"""
CVParser — importazione profilo da CV in PDF.

Stesso pattern già usato per lo scraping (RF3): si estrae il testo grezzo
(qui con pypdf, non un parser di layout) e lo si passa all'LLM, che si
occupa di dargli struttura. Se il CV ha un formato insolito o multi-colonna,
il testo può uscire un po' disordinato ma l'LLM è comunque in grado di
ricavarci le informazioni — non serve un parser di impaginazione sofisticato.

Due compiti separati sul testo estratto:
  1. Strutturazione — anagrafica/esperienze/formazione/skill in JSON.
     Il chiamante NON scrive nulla sul profilo: il frontend mostra
     un'anteprima e l'utente conferma cosa applicare.
  2. Critica — feedback onesto sul CV originale, mostrato in un pannello
     informativo separato, non tocca il profilo.
"""
import io
import logging

from pypdf import PdfReader

from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

MAX_CHARS = 12000  # limite prompt — un CV ha più segnale/meno rumore di una pagina web


class CVParser:
    def __init__(self, llm: LLMGateway):
        self.llm = llm

    @staticmethod
    def extract_text(pdf_bytes: bytes) -> str:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()

    async def extract_profile(self, raw_text: str) -> dict:
        prompt = (
        "Analizza questo CV ed estrai le informazioni in JSON.\n"
        "Usa SOLO informazioni presenti nel testo, non inventare NULLA. "
        "Se un'informazione non c'è, usa null o ometti il campo.\n\n"
        'Rispondi SOLO con un oggetto JSON con queste chiavi:\n'
        '  "name": nome e cognome\n'
        '  "email": email\n'
        '  "phone": telefono (null se assente)\n'
        '  "location": città o zona (null se assente)\n'
        '  "bio": due righe di sintesi professionale ricavate dal CV (null se non ricavabile)\n'
        '  "hard_skills": array di stringhe — competenze tecniche, strumenti, linguaggi\n'
        '  "soft_skills": array di stringhe\n'
        '  "languages": array di oggetti {"language","level"} — lingua e livello CEFR '
        '(A1/A2/B1/B2/C1/C2/madrelingua). Esempio: {"language":"english","level":"B2"}\n'
        '  "experiences": array di oggetti '
        '{"company","role","start_date","end_date","description"}\n'
        '  "education": array di oggetti {"institution","degree","field","year"}\n\n'
        f"TESTO CV:\n{raw_text[:MAX_CHARS]}"
        )
        data = await self.llm.complete_json(prompt, default={})
        if not isinstance(data, dict):
            data = {}
        return self._normalize(data)

    async def critique(self, raw_text: str) -> str | None:
        prompt = (
            "Sei un recruiter esperto. Analizza criticamente questo CV e scrivi "
            "un feedback onesto e utile in italiano, in elenco puntato "
            "(massimo 8 punti).\n"
            "Copri: cosa manca, cosa è debole o vago, cosa migliorare nella forma "
            "(struttura, quantificazione dei risultati, chiarezza). Sii diretto e "
            "concreto, non generico.\n\n"
            f"TESTO CV:\n{raw_text[:MAX_CHARS]}"
        )
        try:
            return await self.llm.complete(prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Critica CV non disponibile: %s", exc)
            return None

    # -----------------------------------------------------------------
    @staticmethod
    def _normalize(data: dict) -> dict:
        """L'LLM a volte sbaglia i tipi (stringa invece di lista, ecc.) —
        non deve mai far fallire la response verso il frontend."""

        def _str_list(key: str) -> list[str]:
            val = data.get(key)
            if not isinstance(val, list):
                return []
            return [str(x).strip() for x in val if x and str(x).strip()]

        def _dict_list(key: str, fields: tuple[str, ...]) -> list[dict]:
            val = data.get(key)
            out = []
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        out.append({f: item.get(f) for f in fields})
            return out

        return {
            "name": data.get("name") or None,
            "email": data.get("email") or None,
            "phone": data.get("phone") or None,
            "location": data.get("location") or None,
            "bio": data.get("bio") or None,
            "languages": _dict_list("languages", ("language", "level")),
            "hard_skills": _str_list("hard_skills"),
            "soft_skills": _str_list("soft_skills"),
            "experiences": _dict_list(
                "experiences", ("company", "role", "start_date", "end_date", "description")
            ),
            "education": _dict_list(
                "education", ("institution", "degree", "field", "year")
            ),
        }
