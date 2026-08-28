"""
Router: CV e lettera "base" dell'utente.

Il CV base è il testo da cui derivano tutte le versioni per singola
azienda. Sostituisce la bio scritta a mano: `User.bio` resta nel modello
perché la leggono il matching semantico (`matcher.py`) e il generatore di
documenti, ma smette di essere un campo da compilare e viene ricavata dal
CV una volta sola.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import verify_token
from app import models, schemas
from app.database import get_db
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users/{user_id}/base-documents", tags=["Documenti base"], dependencies=[Depends(verify_token)],)

DOC_TYPES = ("cv", "cover_letter")


def _get(db: Session, user_id: str, doc_type: str) -> models.BaseDocument | None:
    return (
        db.query(models.BaseDocument)
        .filter(
            models.BaseDocument.user_id == user_id,
            models.BaseDocument.doc_type == doc_type,
        )
        .first()
    )


@router.get("", response_model=list[schemas.BaseDocumentOut])
def list_base_documents(user_id: str, db: Session = Depends(get_db)):
    return (
        db.query(models.BaseDocument)
        .filter(models.BaseDocument.user_id == user_id)
        .all()
    )


@router.put("/{doc_type}", response_model=schemas.BaseDocumentOut)
def upsert_base_document(
    user_id: str, doc_type: str, payload: schemas.BaseDocumentIn,
    db: Session = Depends(get_db),
):
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"Tipo non valido: usa {' o '.join(DOC_TYPES)}")

    doc = _get(db, user_id, doc_type)
    if doc is None:
        doc = models.BaseDocument(user_id=user_id, doc_type=doc_type)
        db.add(doc)
    doc.content = payload.content
    doc.source = payload.source
    db.commit()
    db.refresh(doc)
    return doc


@router.post("/bio/regenerate")
async def regenerate_bio(user_id: str, db: Session = Depends(get_db)):
    """Ricava la bio professionale dal CV base.

    È il rimpiazzo del campo che l'utente compilava a mano: due righe
    scritte una volta invecchiano, mentre il CV viene aggiornato — meglio
    che la sintesi segua il CV invece di vivere di vita propria."""
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")

    cv = _get(db, user_id, "cv")
    if not cv or not cv.content:
        raise HTTPException(
            400, "Nessun CV base: caricane uno prima di generare la sintesi"
        )

    llm = LLMGateway(db=db)
    prompt = (
        "Da questo CV, scrivi DUE righe di sintesi professionale in prima "
        "persona implicita (senza 'Sono'), come l'intestazione di un "
        "profilo. Concreta e senza aggettivi di circostanza.\n"
        "Rispondi solo con le due righe, in italiano.\n\n"
        f"CV:\n{cv.content[:8000]}"
    )
    try:
        bio = await llm.complete(prompt)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Generazione bio fallita: %s", exc)
        raise HTTPException(503, "LLM non disponibile in questo momento")

    if bio:
        user.bio = bio.strip()[:600]
        db.commit()
    return {"bio": user.bio}
