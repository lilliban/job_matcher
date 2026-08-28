"""
Cleanup automatico dei file esportati — event listener SQLAlchemy.

Quando un GeneratedDocument viene cancellato dal DB (match scartato,
sessione eliminata, ecc.) i PDF/DOCX/MD/TXT già esportati in output/
diventerebbero orfani. Il path non è salvato in DB: viene ricalcolato
con lo stesso stem deterministico usato in fase di export
(DocumentGenerator.output_stem) e rimosso via glob.

Registrato come mapper event così scatta automaticamente per QUALSIASI
cancellazione — diretta o a cascata da Match/SearchSession — senza dover
richiamare la pulizia in ogni router.
"""
import logging

from sqlalchemy import event, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper

from app.core.config import OUTPUT_DIR
from app.models import GeneratedDocument, JobListing, Match
from app.services.doc_generator import DocumentGenerator

logger = logging.getLogger(__name__)


def _cleanup_exported_files(
    mapper: Mapper, connection: Connection, target: GeneratedDocument
) -> None:
    """before_delete — non deve MAI sollevare: un errore qui abortirebbe
    la cancellazione del record dal DB. Usa `connection` (non la Session)
    perché siamo dentro un evento di flush."""
    try:
        row = connection.execute(
            select(JobListing.company_name, JobListing.title)
            .select_from(Match)
            .join(JobListing, JobListing.id == Match.listing_id)
            .where(Match.id == target.match_id)
        ).first()
        if row is None:
            return  # match o annuncio già andati — niente stem da ricostruire

        stem = DocumentGenerator.output_stem(
            target.doc_type, row.company_name, row.title, target.id
        )
        for path in OUTPUT_DIR.glob(f"{stem}.*"):
            try:
                path.unlink()
                logger.info("File orfano rimosso: %s", path.name)
            except OSError as exc:
                logger.warning("Impossibile rimuovere %s: %s", path, exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cleanup file per documento %s fallito: %s", target.id, exc)


event.listen(GeneratedDocument, "before_delete", _cleanup_exported_files)
