"""
Router: candidatura da link — CV e lettera su misura per UN annuncio,
secondo linee guida/schema forniti dall'utente (testo e/o file).

Non tocca il DB oltre alla lettura del profilo: i documenti non vengono
salvati, l'export è senza stato (il frontend rimanda il testo).
"""
import logging
import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.core.security import verify_token
from app.database import get_db
from app.services.application_builder import (
    ApplicationBuilder,
    ApplicationBuilderError,
    build_user_profile,
    extract_file_text,
)
from app.services.doc_generator import DocumentGenerator
from app.services.llm_gateway import LLMGateway, LLMGatewayError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/applications",
    tags=["Candidature da link"],
    dependencies=[Depends(verify_token)],
)

ALLOWED_DOC_TYPES = ("cv", "cover_letter")
MAX_GUIDELINE_FILES = 5
MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown",
    "txt": "text/plain",
}


class ExportRequest(BaseModel):
    content: str = Field(min_length=1)
    fmt: str = "pdf"
    name: str = "documento"


@router.post("/generate")
async def generate_application(
    user_id: str = Form(...),
    url: Optional[str] = Form(None),
    job_text: Optional[str] = Form(None),
    guidelines: Optional[str] = Form(None),
    doc_types: str = Form("cv,cover_letter"),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "Utente non trovato")

    wanted = [d.strip() for d in doc_types.split(",") if d.strip()]
    if not wanted or any(d not in ALLOWED_DOC_TYPES for d in wanted):
        raise HTTPException(400, f"doc_types ammessi: {', '.join(ALLOWED_DOC_TYPES)}")
    if len(files) > MAX_GUIDELINE_FILES:
        raise HTTPException(400, f"Massimo {MAX_GUIDELINE_FILES} file di linee guida")

    # Linee guida = testo scritto + testo estratto dai file, in un unico blocco
    parts: list[str] = []
    if guidelines and guidelines.strip():
        parts.append(guidelines.strip())
    for f in files:
        try:
            text = extract_file_text(f.filename or "file", await f.read())
        except ApplicationBuilderError as exc:
            raise HTTPException(400, str(exc)) from exc
        parts.append(f"[File: {f.filename}]\n{text}")
    combined_guidelines = "\n\n".join(parts)

    llm = LLMGateway(db=db)
    builder = ApplicationBuilder(llm)
    try:
        listing = await builder.fetch_listing(url, job_text)
    except ApplicationBuilderError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMGatewayError as exc:
        raise HTTPException(503, str(exc)) from exc

    profile = build_user_profile(user)
    gen = DocumentGenerator(llm)
    documents: dict[str, str] = {}
    try:
        for doc_type in wanted:
            documents[doc_type] = await gen.generate(
                doc_type, profile, listing, None, guidelines=combined_guidelines
            )
    except LLMGatewayError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Generazione candidatura fallita")
        raise HTTPException(500, f"Generazione fallita: {exc}") from exc

    return {
        "listing": listing,
        "documents": documents,
        "guidelines_chars": len(combined_guidelines),
        "llm_model": llm.last_model_used,
    }


@router.post("/export")
def export_application_document(payload: ExportRequest):
    if payload.fmt not in MEDIA_TYPES:
        raise HTTPException(400, f"Formato non valido. Ammessi: {', '.join(MEDIA_TYPES)}")

    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", payload.name)[:60] or "documento"
    stem = f"{safe}_{uuid.uuid4().hex[:8]}"
    try:
        path = DocumentGenerator.export(payload.content, payload.fmt, stem)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Export candidatura fallito")
        raise HTTPException(500, f"Export fallito: {exc}") from exc
    return FileResponse(
        path=str(path), media_type=MEDIA_TYPES[payload.fmt], filename=path.name
    )
