"""
Copia una tantum dei dati da job_matcher.db (SQLite) a PostgreSQL.

    docker compose up -d
    # imposta DATABASE_URL in .env sulla stringa Postgres (vedi .env.example)
    python scripts/migrate_sqlite_to_postgres.py

Legge sempre dal file SQLite in root (indipendentemente da cosa dice
DATABASE_URL in quel momento) e scrive nel Postgres indicato da
DATABASE_URL — quindi DATABASE_URL deve già puntare a Postgres quando lo
lanci. Usa gli stessi modelli ORM per creare lo schema di destinazione,
poi copia riga per riga nell'ordine che rispetta le foreign key (i
genitori prima dei figli).

Le chiavi primarie sono UUID generati in Python (gen_id(), vedi
models/domain.py), non interi autoincrementanti: non c'è quindi bisogno
di rimappare gli id tra sorgente e destinazione. `session.merge()` fa un
upsert per chiave primaria, quindi lo script è rilanciabile senza
duplicare nulla se si interrompe a metà.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import BASE_DIR, DATABASE_URL  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    BaseDocument,
    CompanyCollection,
    CompanyCollectionMember,
    CompanyProfile,
    Education,
    Experience,
    GeneratedDocument,
    JobListing,
    JobPosting,
    LLMCache,
    Match,
    SearchLog,
    SearchSession,
    SessionHardSkill,
    SoftSkill,
    TargetCompany,
    User,
    UserHardSkill,
    UserLanguage,
    UserPreferredCompany,
)

# Genitori prima dei figli — una FK verso una riga non ancora copiata
# farebbe fallire l'insert su Postgres (SQLite non la controlla mai).
TABLES_IN_ORDER = [
    User,
    UserLanguage,
    SoftSkill,
    UserHardSkill,
    Experience,
    Education,
    UserPreferredCompany,
    BaseDocument,
    CompanyCollection,
    CompanyCollectionMember,
    CompanyProfile,
    SearchSession,
    SessionHardSkill,
    TargetCompany,
    JobPosting,
    JobListing,
    Match,
    GeneratedDocument,
    SearchLog,
    LLMCache,
]


def main() -> None:
    if not DATABASE_URL.startswith("postgresql"):
        print(
            "DATABASE_URL non punta a Postgres (valore attuale: "
            f"{DATABASE_URL}). Impostalo in .env prima di eseguire "
            "questo script — vedi .env.example."
        )
        sys.exit(1)

    sqlite_path = BASE_DIR / "job_matcher.db"
    if not sqlite_path.exists():
        print(f"Nessun database SQLite trovato in {sqlite_path}, niente da migrare.")
        sys.exit(1)

    src_engine = create_engine(f"sqlite:///{sqlite_path}")
    dst_engine = create_engine(DATABASE_URL)

    print(f"Sorgente : {sqlite_path}")
    print(f"Destinazione: {DATABASE_URL.split('@')[-1]}")  # non stampa la password

    Base.metadata.create_all(bind=dst_engine)

    SrcSession = sessionmaker(bind=src_engine)
    DstSession = sessionmaker(bind=dst_engine)
    src, dst = SrcSession(), DstSession()

    try:
        for model in TABLES_IN_ORDER:
            rows = src.query(model).all()
            for row in rows:
                data = {c.name: getattr(row, c.name) for c in model.__table__.columns}
                dst.merge(model(**data))
            dst.commit()
            print(f"  {model.__tablename__}: {len(rows)} righe copiate")
    finally:
        src.close()
        dst.close()

    print("Migrazione completata.")


if __name__ == "__main__":
    main()
