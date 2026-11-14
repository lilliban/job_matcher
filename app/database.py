"""
Configurazione SQLAlchemy — SQLite locale, zero costi, zero setup.
"""
import logging
import time
import threading 
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL

# Aggiungi logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,  # Metti True per vedere TUTTE le query SQL
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency FastAPI: una sessione DB per request."""
    start_time = time.time()
    db = SessionLocal()
    logger.info(f"🔵 Connessione DB aperta (thread: {threading.current_thread().name})")
    
    try:
        yield db
    except Exception as e:
        logger.error(f"🔴 ERRORE DATABASE: {type(e).__name__}: {e}")
        raise
    finally:
        duration = time.time() - start_time
        if duration > 0.5:  # se dura più di 500ms
            logger.warning(f"⚠️ Connessione DB lenta: {duration:.2f}s")
        logger.info(f"⚪ Connessione DB chiusa ({duration:.3f}s)")
        db.close()

def ensure_schema() -> None:
    """Aggiunge le colonne introdotte dopo la creazione del database.

    `create_all` non altera mai le tabelle esistenti, e dover ricordare di
    lanciare scripts/migrate.py a mano significava vedere l'app rompersi
    con "no such column". Qui si fa solo ciò che è sicuro: ADD COLUMN, solo
    se la colonna manca, senza toccare i dati."""
    from sqlalchemy import text

    additions = [
        ("search_sessions", "search_mode", "VARCHAR DEFAULT 'both'"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in additions:
            cols = {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})"))}
            if cols and column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
                logger.info("Schema aggiornato: %s.%s", table, column)
