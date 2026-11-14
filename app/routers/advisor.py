"""
Router: suggerimenti sul profilo (ruoli, competenze, carenze, novità).
Vedi app/services/career_advisor.py.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.database import get_db
from app.routers.users import get_user_or_404
from app.services import career_advisor
from app.services.llm_gateway import LLMGateway

router = APIRouter(
    prefix="/api/users/{user_id}/advisor",
    tags=["Suggerimenti"],
    dependencies=[Depends(verify_token)],
)


def _parse_since(since: Optional[str]) -> datetime | None:
    if not since:
        return None
    try:
        return datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


@router.get("/roles")
async def roles(
    user_id: str,
    since: Optional[str] = Query(default=None, description="ISO date: conta le novità da qui"),
    country: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Ruoli adatti al profilo, ciascuno col numero di annunci nuovi."""
    user = get_user_or_404(db, user_id)
    items = await career_advisor.suggest_roles(LLMGateway(db=db), user)
    news = career_advisor.new_postings(
        db, _parse_since(since), [i["role"] for i in items], country
    )
    counts = {r["role"]: r["count"] for r in news["per_role"]}
    for i in items:
        i["new_postings"] = counts.get(i["role"], 0)
    return {"roles": items, "news": news}


@router.get("/skills")
async def skills(user_id: str, db: Session = Depends(get_db)):
    """Competenze probabili che il profilo non riporta."""
    user = get_user_or_404(db, user_id)
    return {"skills": await career_advisor.suggest_skills(LLMGateway(db=db), user)}


@router.get("/skills/similar")
async def similar(user_id: str, name: str, db: Session = Depends(get_db)):
    """Competenze collegate a quella appena aggiunta."""
    user = get_user_or_404(db, user_id)
    return {"skills": await career_advisor.similar_skills(LLMGateway(db=db), user, name)}


@router.get("/role-gap")
async def role_gap(user_id: str, role: str, db: Session = Depends(get_db)):
    """Carenza rispetto a un ruolo. `show` è vero solo se è seria."""
    user = get_user_or_404(db, user_id)
    return await career_advisor.role_gap(LLMGateway(db=db), user, role)
