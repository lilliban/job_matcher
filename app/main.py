"""
JobMatcher — Backend API

Avvio:  python run.py
Docs:   http://localhost:8000/docs
App:    http://localhost:8000
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import GEMINI_API_KEY, GOOGLE_PLACES_API_KEY, OLLAMA_MODEL
from app.database import Base, engine
from app.routers import (
    base_documents,
    collections,
    companies,
    discovery,
    documents,
    geo,
    matches,
    sessions,
    skills,
    users,
)
from app.services import document_cleanup  # noqa: F401 — registra il cleanup automatico dei file esportati

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database inizializzato")

    if GEMINI_API_KEY:
        logger.info("LLM primario: Gemini")
    else:
        logger.warning(
            "GEMINI_API_KEY non configurata → uso Ollama locale (%s). "
            "Assicurati che 'ollama serve' sia attivo.", OLLAMA_MODEL
        )
    if not GOOGLE_PLACES_API_KEY:
        logger.info(
            "GOOGLE_PLACES_API_KEY non configurata → verifica aziende disabilitata "
            "(il sistema funziona comunque, con meno precisione sulle PMI locali)"
        )
    yield


app = FastAPI(
    title="JobMatcher API",
    description=(
        "Sistema di ricerca lavoro automatizzata con matching AI, "
        "generazione CV e cover letter su misura, e report di intelligence."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[   
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ], 
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)



@app.get("/api/health", tags=["System"])
def health():
    return {
        "status": "ok",
        "llm_primary": "gemini" if GEMINI_API_KEY else "ollama",
        "places_enabled": bool(GOOGLE_PLACES_API_KEY),
    }

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    # Restituisce No Content evitando il 404 nei log
    from fastapi import Response
    return Response(status_code=204)

app.include_router(users.router)
app.include_router(skills.router)
app.include_router(sessions.router)
app.include_router(companies.router)
app.include_router(matches.router)
app.include_router(documents.router)
app.include_router(geo.router)
# discovery espone gli stessi motori di companies.router ma a livello
# utente: serve a poter scegliere competenze e aziende PRIMA di creare la
# ricerca (vedi app/routers/discovery.py)
app.include_router(discovery.router)
app.include_router(base_documents.router)
app.include_router(collections.router)


# ---------------------------------------------------------------------
# Frontend statico
# ---------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
