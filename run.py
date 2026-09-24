"""
Entry point — avvia il server con uvicorn.

    python run.py

Opzioni ambiente (facoltative):
    HOST=127.0.0.1  PORT=8000
    RELOAD=1        # hot reload del backend quando cambiano i file .py in app/
"""
import os
import sys

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print(
            "\n[!] Le dipendenze non sono installate.\n"
            "    Esegui prima:  pip install -r requirements.txt\n"
        )
        sys.exit(1)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "").lower() in {"1", "true", "yes"}

    # ASCII di proposito: su Windows stdout usa la codepage della console
    # (cp1252 quando l'output è rediretto su file), e una freccia unicode
    # faceva morire l'avvio con UnicodeEncodeError prima ancora di partire.
    print(f"\n  JobMatcher -> http://{host}:{port}")
    print(f"  Docs API   -> http://{host}:{port}/docs")
    if reload:
        print("  Hot reload attivo (RELOAD=1)")
    print()

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=["app"] if reload else None,
    )
