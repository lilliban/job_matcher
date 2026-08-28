"""
Test per riprodurre il problema del database locked.

Versione corretta con la struttura reale del database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import threading
import time
from sqlalchemy import text

from app.database import SessionLocal


def create_test_table():
    """Crea una tabella di test dedicata."""
    db = SessionLocal()
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS test_lock (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.commit()
        print(" Tabella di test pronta")
    except Exception as e:
        print(f" Errore creazione tabella: {e}")
        db.rollback()
    finally:
        db.close()

#duration è quanti secondi deve lavorare
def simulate_writer(writer_id: int, duration: int = 10):
    """Simula il SearchRunner che scrive nel DB."""
    print(f"  Writer {writer_id} avviato")
    db = SessionLocal()
    
    end_time = time.time() + duration
    count = 0
    errors = 0
    
    try:
        while time.time() < end_time:
            try:
                db.execute(text(
                    "INSERT INTO test_lock (data) VALUES ('test write')"
                ))
                db.commit()
                count += 1
                time.sleep(0.2)
            except Exception as e:
                print(f" WRITER {writer_id} ERRORE: {type(e).__name__}: {e}")
                errors += 1
                db.rollback()
                time.sleep(0.5)
    
    finally:
        db.close()
        print(f"Writer {writer_id} finito: {count} scritture, {errors} errori")


def simulate_reader(reader_id: int, duration: int = 10):
    """Simula il frontend che legge dal DB."""
    print(f"Reader {reader_id} avviato")
    db = SessionLocal()
    
    end_time = time.time() + duration
    count = 0
    errors = 0
    
    try:
        while time.time() < end_time:
            try:
                result = db.execute(text("SELECT COUNT(*) FROM test_lock"))
                result.fetchone()
                count += 1
                time.sleep(0.1)
            except Exception as e:
                print(f"READER {reader_id} ERRORE: {type(e).__name__}: {e}")
                errors += 1
                time.sleep(0.5)
    
    finally:
        db.close()
        print(f"Reader {reader_id} finito: {count} letture, {errors} errori")


def test_writer_reader():
    """Test: 1 writer + 2 reader in parallelo."""
    print("=" * 60)
    print("TEST: 1 Writer + 2 Reader simultanei")
    print("=" * 60)
    
    threads = [
        threading.Thread(target=simulate_writer, args=(1, 10), name="Writer-1"),
        threading.Thread(target=simulate_reader, args=(1, 10), name="Reader-1"),
        threading.Thread(target=simulate_reader, args=(2, 10), name="Reader-2"),
    ]
    
    start = time.time()
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    duration = time.time() - start
    print(f"\n Durata: {duration:.2f}s")
    print("Test completato\n")


def test_multiple_writers():
    """Test: 3 writer simultanei (caso peggiore)."""
    print("=" * 60)
    print("TEST: 3 Writer simultanei")
    print("=" * 60)
    
    threads = [
        threading.Thread(target=simulate_writer, args=(i+1, 5), name=f"Writer-{i+1}")
        for i in range(3)
    ]
    
    start = time.time()
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    duration = time.time() - start
    print(f"\n Durata: {duration:.2f}s")
    print("Test completato\n")


def cleanup():
    """Rimuove la tabella di test."""
    db = SessionLocal()
    try:
        db.execute(text("DROP TABLE IF EXISTS test_lock"))
        db.commit()
        print("🧹 Tabella di test rimossa")
    finally:
        db.close()


if __name__ == "__main__":
    print("TEST DIAGNOSTICO DATABASE LOCKED")
    print("=" * 60)
    print()
    
    # Crea tabella test
    create_test_table()
    print()
    
    # Test 1: Writer + Reader
    test_writer_reader()
    
    # Test 2: Multipli writer
    test_multiple_writers()
    
    # Pulizia
    cleanup()
    
    print()
    print("=" * 60)
    print("RISULTATO:")
    print("Se vedi '0 errori' ovunque → NESSUN problema di lock")
    print("Se vedi 'database is locked' → Il problema esiste")
    print("=" * 60)