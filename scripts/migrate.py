"""
Migrazioni schema — idempotenti, da eseguire a mano.

    python scripts/migrate.py

Perché esiste (vedi ADR-017): `Base.metadata.create_all()` in app/main.py
emette solo CREATE TABLE. **Non aggiunge mai colonne a tabelle esistenti.**
Quindi aggiungere un campo a un modello già presente nel DB fa fallire ogni
SELECT dell'ORM con "no such column", su un database che contiene dati veri.

Alembic è installato in .venv ma non è configurato (nessun alembic.ini,
nessuna cartella migrations/, non è in requirements.txt). Introdurlo per un
progetto a utente singolo con un file SQLite contraddice ADR-001, quindi si
resta su ALTER TABLE espliciti.

Ogni migrazione è una funzione che:
  - controlla lo stato con PRAGMA table_info prima di agire
  - può essere rieseguita all'infinito senza effetti collaterali
  - non cancella e non riscrive mai dati esistenti

Prima di eseguire, fai una copia di job_matcher.db.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, text  # noqa: E402

from app.database import Base, engine  # noqa: E402
import app.models  # noqa: F401,E402  — registra i modelli su Base.metadata


def _columns(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    ).fetchone()
    return row is not None


def add_column(conn, table: str, column: str, ddl_type: str) -> bool:
    """ALTER TABLE ... ADD COLUMN, solo se la colonna manca davvero."""
    if not _table_exists(conn, table):
        print(f"  · {table}: tabella non presente, la creerà create_all")
        return False
    if column in _columns(conn, table):
        print(f"  = {table}.{column}: già presente")
        return False
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
    print(f"  + {table}.{column}: aggiunta ({ddl_type})")
    return True


# ---------------------------------------------------------------------
# Migrazioni
# ---------------------------------------------------------------------
def m001_company_profile_link(conn) -> None:
    """Fase 1.3 — TargetCompany punta al registro aziende globale.

    Il registro (company_profiles) tiene i dati costosi da scoprire —
    careers_url, provider ATS, slug — che prima vivevano solo dentro una
    sessione e venivano riscoperti da zero a ogni nuova ricerca."""
    add_column(conn, "target_companies", "company_profile_id", "VARCHAR")


def m002_target_company_search_state(conn) -> None:
    """Fase 2.2 — ogni azienda target ricorda quando è stata cercata
    l'ultima volta e com'è andata, così la vista di una ricerca aperta può
    mostrarlo e il re-run può saltare ciò che è ancora fresco."""
    add_column(conn, "target_companies", "last_searched_at", "DATETIME")
    add_column(conn, "target_companies", "last_result", "VARCHAR")
    add_column(conn, "target_companies", "last_postings_count", "INTEGER")


def m003_job_posting_link(conn) -> None:
    """Fase 1.5 — JobListing diventa il legame sessione↔annuncio.

    Le colonne di contenuto restano dov'erano e continuano a essere
    riempite: la vista Risultati e i Match esistenti le leggono da lì, e
    riscriverli avrebbe messo a rischio 274 annunci, 30 match e 88
    documenti reali per un guadagno di sola eleganza (ADR-020)."""
    add_column(conn, "job_listings", "posting_id", "VARCHAR")


def m004_backfill_postings(conn) -> None:
    """Popola job_postings dagli annunci già raccolti, raggruppando per
    content_hash, e collega le righe esistenti.

    Idempotente: salta gli hash già presenti e le righe già collegate.
    Gli annunci storici non hanno i campi normalizzati (non c'era il codice
    che li estraeva quando sono stati raccolti) — restano NULL, e si
    riempiranno alla prossima raccolta."""
    if not _table_exists(conn, "job_postings"):
        print("  · job_postings non presente, salto il backfill")
        return

    rows = conn.execute(text("""
        SELECT content_hash,
               MIN(id)            AS any_id,
               MIN(title)         AS title,
               MIN(company_name)  AS company_name,
               MIN(source_url)    AS source_url,
               MIN(source_board)  AS source_board,
               MIN(description)   AS description,
               MIN(requirements_raw) AS requirements_raw,
               MIN(location)      AS location,
               MIN(contract_type) AS contract_type,
               MIN(posted_date)   AS posted_date,
               MIN(scraped_at)    AS first_seen
          FROM job_listings
         WHERE content_hash IS NOT NULL
           AND posting_id IS NULL
      GROUP BY content_hash
    """)).mappings().all()

    created = 0
    for r in rows:
        existing = conn.execute(
            text("SELECT id FROM job_postings WHERE content_hash = :h"),
            {"h": r["content_hash"]},
        ).fetchone()
        if existing:
            pid = existing[0]
        else:
            pid = str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO job_postings
                    (id, content_hash, title, company_name, source_url,
                     source_board, source_kind, description, requirements_raw,
                     location, contract_type, posted_date,
                     first_seen_at, last_seen_at, consecutive_misses, is_closed)
                VALUES
                    (:id, :h, :title, :company, :url, :board, 'board', :descr,
                     :req, :loc, :contract, :posted, :seen, :seen, 0, 0)
            """), {
                "id": pid, "h": r["content_hash"], "title": r["title"] or "",
                "company": r["company_name"] or "N/D", "url": r["source_url"],
                "board": r["source_board"], "descr": r["description"],
                "req": r["requirements_raw"], "loc": r["location"],
                "contract": r["contract_type"], "posted": r["posted_date"],
                "seen": r["first_seen"],
            })
            created += 1

        conn.execute(
            text("UPDATE job_listings SET posting_id = :pid "
                 "WHERE content_hash = :h AND posting_id IS NULL"),
            {"pid": pid, "h": r["content_hash"]},
        )

    orphans = conn.execute(
        text("SELECT COUNT(*) FROM job_listings WHERE posting_id IS NULL")
    ).scalar()
    print(f"  + job_postings: {created} creati da {len(rows)} hash distinti "
          f"({orphans} annunci senza hash restano scollegati)")


def m005_session_geo(conn) -> None:
    """Fase 3 — geografia strutturata sulla sessione.

    `preferred_country` e `location_pref` restano e continuano a essere
    scritti: sono ciò che la costruzione degli URL dei portali legge, e le
    15 sessioni già nel database non hanno i campi nuovi."""
    add_column(conn, "search_sessions", "geo_scope", "VARCHAR")
    add_column(conn, "search_sessions", "geo_country", "VARCHAR")
    add_column(conn, "search_sessions", "geo_region", "VARCHAR")


def m006_base_documents(conn) -> None:
    """Fase 2 — il CV base vive in una tabella nuova, creata da create_all;
    qui non serve nessun ALTER. La funzione esiste per lasciare traccia
    della migrazione nella sequenza."""
    print("  · base_documents: tabella nuova, la crea create_all")


MIGRATIONS = [
    ("001_company_profile_link", m001_company_profile_link),
    ("002_target_company_search_state", m002_target_company_search_state),
    ("003_job_posting_link", m003_job_posting_link),
    ("004_backfill_postings", m004_backfill_postings),
    ("005_session_geo", m005_session_geo),
    ("006_base_documents", m006_base_documents),
]


def main() -> int:
    db_path = engine.url.database
    if db_path and not Path(db_path).exists():
        print(f"Database non trovato in {db_path} — verrà creato da zero.")

    print("Creazione tabelle mancanti (create_all)...")
    Base.metadata.create_all(bind=engine)

    print("\nMigrazioni colonne:")
    with engine.begin() as conn:
        for name, fn in MIGRATIONS:
            print(f"\n[{name}]")
            fn(conn)

    print("\nVerifica finale:")
    insp = inspect(engine)
    for table in ("company_profiles", "target_companies"):
        if table in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns(table)]
            print(f"  {table}: {len(cols)} colonne")
        else:
            print(f"  {table}: ASSENTE")

    print("\nFatto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
