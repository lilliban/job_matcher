"""
JobMatcher — Backend API

Avvio:  python run.py
Docs:   http://localhost:8000/docs
App:    http://localhost:8000
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import GEMINI_API_KEY, GOOGLE_PLACES_API_KEY, OLLAMA_MODEL
from app.database import Base, engine, ensure_schema
from app.routers import (
    advisor,
    applications,
    base_documents,
    collections,
    companies,
    discovery,
    documents,
    geo,
    onboarding,
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
    ensure_schema()
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
app.include_router(applications.router)
app.include_router(advisor.router)
app.include_router(onboarding.router)
app.include_router(discovery.catalog_router)


# ---------------------------------------------------------------------
# Frontend
#
# L'interfaccia è la SPA React in frontend/ (si compila con `npm run build`
# in frontend/, che scrive in frontend/dist). Se la build non c'è si dice
# cosa fare, invece di servire in silenzio la vecchia interfaccia.
# La vecchia SPA vanilla resta in frontend/legacy, raggiungibile su /legacy.
# ---------------------------------------------------------------------
DIST_DIR = FRONTEND_DIR / "dist"
LEGACY_DIR = FRONTEND_DIR / "legacy"

if LEGACY_DIR.exists():
    app.mount("/static/legacy", StaticFiles(directory=str(LEGACY_DIR)), name="legacy-static")

    @app.get("/legacy", include_in_schema=False)
    def serve_legacy():
        return FileResponse(str(LEGACY_DIR / "index.html"))

if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def serve_spa(path: str):
        """Qualunque percorso non-API apre la SPA (il router è lato client);
        un file reale in dist (favicon, ecc.) viene servito così com'è."""
        if path.startswith("api/"):
            raise HTTPException(404, "Endpoint non trovato")
        candidate = (DIST_DIR / path).resolve()
        if path and candidate.is_file() and DIST_DIR.resolve() in candidate.parents:
            return FileResponse(str(candidate))
        return FileResponse(str(DIST_DIR / "index.html"))
else:

    @app.get("/", include_in_schema=False)
    def frontend_not_built():
        return HTMLResponse(
            "<h1>JobMatcher</h1><p>Interfaccia non compilata. Esegui "
            "<code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code> "
            "e ricarica, oppure per sviluppare <code>npm run dev</code> "
            "(porta 5173). Documentazione API: <a href='/docs'>/docs</a>. "
            "Vecchia interfaccia: <a href='/legacy'>/legacy</a>.</p>"
        )
