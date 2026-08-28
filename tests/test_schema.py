"""
Verifica la struttura delle tabelle nel database.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database import SessionLocal


def check_table_structure():
    """Mostra la struttura delle tabelle principali."""
    db = SessionLocal()
    
    try:
        # 1. Mostra tutte le tabelle
        print("=" * 60)
        print("TABELLE NEL DATABASE")
        print("=" * 60)
        
        result = db.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ))
        
        tables = [row[0] for row in result]
        for table in tables:
            print(f"  📁 {table}")
        
        # 2. Mostra struttura di search_logs
        print("\n" + "=" * 60)
        print("STRUTTURA TABELLA: search_logs")
        print("=" * 60)
        
        result = db.execute(text("PRAGMA table_info(search_logs)"))
        columns = result.fetchall()
        
        if columns:
            for col in columns:
                # col: (cid, name, type, notnull, default, pk)
                print(f"  • {col[1]:<20} {col[2]:<15} {'PK' if col[5] else ''}")
        else:
            print("  ❌ Tabella non trovata!")
        
        # 3. Mostra struttura di search_sessions
        print("\n" + "=" * 60)
        print("STRUTTURA TABELLA: search_sessions")
        print("=" * 60)
        
        result = db.execute(text("PRAGMA table_info(search_sessions)"))
        columns = result.fetchall()
        
        if columns:
            for col in columns:
                print(f"  • {col[1]:<20} {col[2]:<15} {'PK' if col[5] else ''}")
        else:
            print("  ❌ Tabella non trovata!")
        
        # 4. Mostra struttura di job_listings
        print("\n" + "=" * 60)
        print("STRUTTURA TABELLA: job_listings")
        print("=" * 60)
        
        result = db.execute(text("PRAGMA table_info(job_listings)"))
        columns = result.fetchall()
        
        if columns:
            for col in columns:
                print(f"  • {col[1]:<20} {col[2]:<15} {'PK' if col[5] else ''}")
        else:
            print("  ❌ Tabella non trovata!")
        
        # 5. Conta record
        print("\n" + "=" * 60)
        print("CONTEGGIO RECORD")
        print("=" * 60)
        
        for table in ["search_logs", "search_sessions", "job_listings"]:
            try:
                result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.fetchone()[0]
                print(f"  • {table}: {count} record")
            except Exception as e:
                print(f"  • {table}: ERRORE ({e})")
    
    finally:
        db.close()


if __name__ == "__main__":
    check_table_structure()