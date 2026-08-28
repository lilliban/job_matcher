"""
Router: documenti generati — RF5.4

Export reale in PDF e DOCX + rigenerazione con istruzioni extra.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session


from app.core.security import verify_token
from app import models, schemas
from app.database import get_db
from app.services.doc_generator import DocumentGenerator
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["Documenti"], dependencies=[Depends(verify_token)],)

VALID_DOC_TYPES = {"cv", "cover_letter", "email"}
VALID_FORMATS = {"pdf", "docx", "md", "txt"}


def get_document_or_404(db: Session, doc_id: str) -> models.GeneratedDocument:
    doc = db.get(models.GeneratedDocument, doc_id)
    if not doc:
        raise HTTPException(404, "Documento non trovato")
    return doc


@router.get("/{doc_id}", response_model=schemas.GeneratedDocumentOut)
def get_document(doc_id: str, db: Session = Depends(get_db)):
    return get_document_or_404(db, doc_id)


@router.get("/{doc_id}/export")
def export_document(
    doc_id: str,
    fmt: str = Query(default="pdf", description="pdf/docx/md/txt"),
    db: Session = Depends(get_db),
):
    """RF5.4 — scarica il documento nel formato richiesto."""
    if fmt not in VALID_FORMATS:
        raise HTTPException(400, f"Formato non valido. Ammessi: {', '.join(VALID_FORMATS)}")

    doc = get_document_or_404(db, doc_id)
    if not doc.content:
        raise HTTPException(400, "Il documento è vuoto")

    match = doc.match
    listing = match.listing if match else None
    stem = DocumentGenerator.output_stem(
        doc.doc_type,
        listing.company_name if listing else "",
        listing.title if listing else "",
        doc.id,
    )

    try:
        path = DocumentGenerator.export(doc.content, fmt, stem)
    except ImportError as exc:
        raise HTTPException(
            500,
            f"Libreria mancante per l'export {fmt}. Installa le dipendenze: {exc}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Export fallito")
        raise HTTPException(500, f"Export fallito: {exc}") from exc

    media_types = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "md": "text/markdown",
        "txt": "text/plain",
    }
    return FileResponse(
        path=str(path),
        media_type=media_types[fmt],
        filename=path.name,
    )


@router.post("/regenerate/{match_id}", response_model=schemas.GeneratedDocumentOut)
async def regenerate_document(
    match_id: str,
    payload: schemas.DocumentRegenerateRequest,
    db: Session = Depends(get_db),
):
    """R05 — l'utente non è soddisfatto: rigenera con istruzioni extra."""
    if payload.doc_type not in VALID_DOC_TYPES:
        raise HTTPException(400, f"Tipo non valido. Ammessi: {', '.join(VALID_DOC_TYPES)}")

    match = db.get(models.Match, match_id)
    if not match:
        raise HTTPException(404, "Match non trovato")

    listing = match.listing
    session = match.session
    user = session.user

    user_profile = {
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
        # Senza questa riga la rigenerazione manuale riscriveva il documento
        # da zero dai dati grezzi, mentre la generazione automatica lo adatta
        # dal CV base (ADR-022): lo stesso pulsante produceva un risultato di
        # natura diversa a seconda di come lo si era ottenuto la prima volta.
        "base_documents": {
            d.doc_type: d.content for d in user.base_documents if d.content
        },
    }

    listing_dict = {
        "title": listing.title,
        "company_name": listing.company_name,
        "location": listing.location,
        "requirements_raw": listing.requirements_raw,
        "description": listing.description,
    }

    match_info = {
        "matched_skills": match.matched_skills,
        "missing_skills": match.missing_skills,
    }

    llm = LLMGateway(db=db)
    gen = DocumentGenerator(llm)

    try:
        content = await gen.generate(payload.doc_type, user_profile, listing_dict, match_info)
        if payload.extra_instructions:
            refine_prompt = (
                "Riscrivi il seguente documento applicando queste istruzioni:\n"
                f"{payload.extra_instructions}\n\n"
                "Mantieni la veridicità: non inventare informazioni.\n\n"
                f"DOCUMENTO ORIGINALE:\n{content}"
            )
            content = await llm.complete(refine_prompt)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Generazione fallita: {exc}") from exc

    # sostituisce il documento esistente dello stesso tipo
    existing = (
        db.query(models.GeneratedDocument)
        .filter(
            models.GeneratedDocument.match_id == match_id,
            models.GeneratedDocument.doc_type == payload.doc_type,
        )
        .first()
    )
    if existing:
        existing.content = content
        existing.llm_model = llm.last_model_used
        db.commit()
        db.refresh(existing)
        return existing

    doc = models.GeneratedDocument(
        match_id=match_id,
        doc_type=payload.doc_type,
        content=content,
        llm_model=llm.last_model_used,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc
