"""
Router: suggerimento skill — RF2.1

Quando l'utente crea una sessione per un ruolo, il sistema propone le
hard skill tipiche di quel ruolo. L'utente spunta quelle che ha.
"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.security import verify_token
from app import schemas
from app.database import get_db
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["Skill"],  dependencies=[Depends(verify_token)], 
                   )

# fallback usato se l'LLM non è disponibile — l'app resta usabile
SOFT_SKILLS_CATALOG = [
    {"name": "Problem solving", "category": "cognitive"},
    {"name": "Comunicazione", "category": "relational"},
    {"name": "Lavoro in team", "category": "relational"},
    {"name": "Gestione del tempo", "category": "organizational"},
    {"name": "Adattabilità", "category": "personal"},
    {"name": "Pensiero critico", "category": "cognitive"},
    {"name": "Leadership", "category": "relational"},
    {"name": "Attenzione ai dettagli", "category": "organizational"},
    {"name": "Autonomia", "category": "personal"},
    {"name": "Gestione dello stress", "category": "personal"},
    {"name": "Negoziazione", "category": "relational"},
    {"name": "Creatività", "category": "cognitive"},
    {"name": "Orientamento al risultato", "category": "organizational"},
    {"name": "Ascolto attivo", "category": "relational"},
    {"name": "Apprendimento continuo", "category": "personal"},
]


@router.get("/soft", response_model=list[schemas.SkillSuggestion])
def list_soft_skills_catalog():
    """RF1.2 — catalogo soft skill da cui l'utente sceglie."""
    return [schemas.SkillSuggestion(**s) for s in SOFT_SKILLS_CATALOG]


@router.get("/soft/{skill_name}/similar", response_model=list[schemas.SkillSuggestion])
async def similar_soft_skills(
    skill_name: str,
    limit: int = Query(default=5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    """Suggerisce soft skill simili/complementari a quella indicata."""
    llm = LLMGateway(db=db)
    prompt = (
        f"Elenca {limit} soft skill simili o complementari a '{skill_name}'.\n"
        "Devono essere competenze trasversali che una persona con quella skill "
        "probabilmente possiede o dovrebbe sviluppare.\n"
        'Rispondi SOLO con un array JSON di oggetti: '
        '[{"name": "...", "category": "...", "importance": "..."}]'
    )
    data = await llm.complete_json(prompt, default=[])

    if not isinstance(data, list) or not data:
        return []

    out = []
    for item in data[:limit]:
        if isinstance(item, dict) and item.get("name"):
            out.append(schemas.SkillSuggestion(
                name=str(item["name"]),
                category=item.get("category"),
                importance=item.get("importance"),
            ))
    return out

@router.get("/suggest", response_model=list[schemas.SkillSuggestion])
async def suggest_skills_for_role(
    role: str = Query(description="Titolo del ruolo, es. 'Data Analyst'"),
    limit: int = Query(default=12, ge=1, le=25),
    db: Session = Depends(get_db),
):
    """RF2.1 — hard skill tipiche del ruolo."""
    llm = LLMGateway(db=db)
    prompt = (
        f"Elenca le {limit} hard skill (competenze tecniche) più richieste "
        f"per il ruolo '{role}' nel mercato del lavoro attuale.\n\n"
        "Includi strumenti, linguaggi, tecnologie e conoscenze specifiche.\n"
        "Non includere soft skill.\n\n"
        'Rispondi SOLO con un array JSON: '
        '[{"name": "...", "category": "...", "importance": "essential|important|nice_to_have"}]'
    )
    data = await llm.complete_json(prompt, default=[])

    if not isinstance(data, list) or not data:
        return []

    out = []
    for item in data[:limit]:
        if isinstance(item, dict) and item.get("name"):
            out.append(schemas.SkillSuggestion(
                name=str(item["name"]),
                category=item.get("category"),
                importance=item.get("importance"),
            ))
    return out
