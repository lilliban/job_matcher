"""
CareerAdvisor — suggerimenti personalizzati sul profilo.

Quattro domande a cui risponde, tutte a partire dal profilo e non da ciò
che l'utente digita:
  - quali ruoli posso cercare?          (suggest_roles)
  - quali competenze mi sto scordando?  (suggest_skills / similar_skills)
  - per questo ruolo ho una carenza seria? (role_gap)
  - cosa c'è di nuovo nell'archivio annunci? (new_postings)

I suggerimenti dell'LLM non vengono mai scritti sul profilo da qui: è
l'utente a scegliere cosa aggiungere.
"""
import logging
import re
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import JobPosting, User
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

# Sotto questa copertura, e con almeno MIN_MISSING competenze assenti, la
# carenza è "seria" e vale la pena interrompere l'utente. Sopra, le
# competenze mancanti si vedono comunque nel dettaglio dei match.
GAP_COVERAGE_THRESHOLD = 0.4
GAP_MIN_MISSING = 4


def _key(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _owned_skills(user: User) -> set[str]:
    return {_key(s.name) for s in user.hard_skills}


def _profile_summary(user: User) -> str:
    lines = []
    if user.bio:
        lines.append(f"Sintesi: {user.bio}")
    if user.hard_skills:
        lines.append("Competenze: " + ", ".join(s.name for s in user.hard_skills))
    for e in user.experiences[:6]:
        desc = (e.description or "")[:200]
        lines.append(f"Esperienza: {e.role} presso {e.company}. {desc}")
    for ed in user.education[:3]:
        lines.append(f"Studi: {ed.degree or ''} {ed.field or ''} ({ed.institution})")
    return "\n".join(lines)


def _list_of_dicts(data, key: str = "name", limit: int = 10) -> list[dict]:
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, dict) and item.get(key):
            out.append(item)
        elif isinstance(item, str) and item.strip():
            out.append({key: item.strip()})
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------
# Ruoli
# ---------------------------------------------------------------------
async def suggest_roles(llm: LLMGateway, user: User, limit: int = 6) -> list[dict]:
    """Ruoli in cui il profilo è spendibile. Ricade sui titoli delle
    esperienze passate se l'LLM non risponde: l'app resta utilizzabile."""
    summary = _profile_summary(user)
    if summary:
        prompt = (
            f"Questo è il profilo di una persona che cerca lavoro:\n{summary}\n\n"
            f"Proponi {limit} ruoli (titoli di lavoro realistici, come compaiono "
            "negli annunci) in cui questo profilo è competitivo, dal più al "
            "meno adatto. Includi anche ruoli vicini a quello attuale in cui "
            "potrebbe non aver pensato. Usa SOLO ciò che emerge dal profilo.\n"
            'Rispondi SOLO con un array JSON: [{"role": "...", "reason": "una frase, perché è adatto"}]'
        )
        try:
            data = await llm.complete_json(prompt, default=[])
        except Exception as exc:  # noqa: BLE001
            logger.info("suggest_roles: LLM non disponibile (%s)", exc)
            data = []
        roles = _list_of_dicts(data, key="role", limit=limit)
        if roles:
            return [
                {"role": str(r["role"]).strip(), "reason": str(r.get("reason") or "").strip()}
                for r in roles
            ]

    seen, out = set(), []
    for e in user.experiences:
        if e.role and _key(e.role) not in seen:
            seen.add(_key(e.role))
            out.append({"role": e.role, "reason": f"Ruolo già ricoperto presso {e.company}"})
    return out[:limit]


# ---------------------------------------------------------------------
# Competenze
# ---------------------------------------------------------------------
async def suggest_skills(llm: LLMGateway, user: User, limit: int = 10) -> list[dict]:
    """Competenze rilevanti per il profilo che l'utente non ha indicato.

    Il caso d'uso è la competenza data per scontata o dimenticata: chi
    lavora con i dati da anni spesso non scrive "Excel" o "Git"."""
    summary = _profile_summary(user)
    if not summary:
        return []
    owned = _owned_skills(user)
    prompt = (
        f"Profilo di una persona che cerca lavoro:\n{summary}\n\n"
        f"Elenca {limit + 5} competenze tecniche (strumenti, linguaggi, "
        "metodologie) che chi ha questo percorso di solito possiede e che "
        "compaiono spesso negli annunci per ruoli affini, ma che NON sono già "
        "nell'elenco delle sue competenze. Una persona può averle usate senza "
        "ricordarsi di indicarle.\n"
        'Rispondi SOLO con un array JSON: [{"name": "...", "why": "perché è probabile che le abbia / perché serve"}]'
    )
    try:
        data = await llm.complete_json(prompt, default=[])
    except Exception as exc:  # noqa: BLE001
        logger.info("suggest_skills: LLM non disponibile (%s)", exc)
        return []

    out = []
    for item in _list_of_dicts(data, limit=limit + 5):
        name = str(item["name"]).strip()
        if _key(name) in owned:
            continue
        out.append({"name": name, "why": str(item.get("why") or "").strip()})
        if len(out) >= limit:
            break
    return out


async def similar_skills(
    llm: LLMGateway, user: User, name: str, limit: int = 6
) -> list[dict]:
    """Competenze che di solito vanno insieme a `name` — mostrate subito
    dopo che l'utente ne aggiunge una, così non se le dimentica."""
    owned = _owned_skills(user) | {_key(name)}
    prompt = (
        f"Una persona ha indicato la competenza '{name}'. Elenca {limit + 4} "
        "competenze tecniche strettamente collegate, che chi la possiede ha "
        "spesso anche o che compaiono insieme a essa negli annunci di lavoro.\n"
        'Rispondi SOLO con un array JSON: [{"name": "..."}]'
    )
    try:
        data = await llm.complete_json(prompt, default=[])
    except Exception as exc:  # noqa: BLE001
        logger.info("similar_skills: LLM non disponibile (%s)", exc)
        return []
    out = []
    for item in _list_of_dicts(data, limit=limit + 4):
        n = str(item["name"]).strip()
        if _key(n) not in owned:
            out.append({"name": n})
        if len(out) >= limit:
            break
    return out


async def role_gap(llm: LLMGateway, user: User, role: str) -> dict:
    """Quanto il profilo copre le competenze tipiche del ruolo.

    `show` è vero solo per una carenza seria: il suggerimento non deve
    comparire a ogni ricerca, altrimenti diventa rumore e l'utente smette
    di leggerlo."""
    owned = _owned_skills(user)
    prompt = (
        f"Elenca le 10 competenze tecniche indispensabili per il ruolo '{role}'.\n"
        'Rispondi SOLO con un array JSON: [{"name": "..."}]'
    )
    try:
        data = await llm.complete_json(prompt, default=[])
    except Exception as exc:  # noqa: BLE001
        logger.info("role_gap: LLM non disponibile (%s)", exc)
        data = []
    required = [str(i["name"]).strip() for i in _list_of_dicts(data, limit=10)]
    if not required:
        return {"role": role, "coverage": None, "missing": [], "show": False}

    def has(req: str) -> bool:
        k = _key(req)
        return any(
            k == o or (len(k) > 2 and k in o) or (len(o) > 2 and o in k)
            for o in owned
        )

    missing = [r for r in required if not has(r)]
    coverage = round(1 - len(missing) / len(required), 2)
    show = coverage < GAP_COVERAGE_THRESHOLD and len(missing) >= GAP_MIN_MISSING
    return {"role": role, "coverage": coverage, "missing": missing, "show": show}


# ---------------------------------------------------------------------
# Novità nell'archivio annunci
# ---------------------------------------------------------------------
def _role_tokens(role: str) -> list[str]:
    return [t for t in re.findall(r"[a-zà-ú0-9+#]+", role.lower()) if len(t) > 2]


def new_postings(
    db: Session,
    since: datetime | None,
    roles: list[str],
    country_code: str | None = None,
    limit: int = 5,
) -> dict:
    """Annunci entrati nell'archivio globale dopo `since`, per i ruoli dati.

    L'archivio (JobPosting) cresce a ogni ricerca di chiunque: è la
    "novità" che l'utente non ha ancora visto, anche senza lanciare nulla."""
    q = db.query(JobPosting).filter(JobPosting.is_closed.is_(False))
    if since:
        q = q.filter(JobPosting.first_seen_at > since)
    if country_code:
        q = q.filter(
            or_(JobPosting.country_code == country_code, JobPosting.country_code.is_(None))
        )

    total = q.count()
    per_role: list[dict] = []
    matched_ids: set[str] = set()
    for role in roles:
        tokens = _role_tokens(role)
        if not tokens:
            continue
        rq = q.filter(or_(*[JobPosting.title.ilike(f"%{t}%") for t in tokens]))
        rows = rq.order_by(JobPosting.first_seen_at.desc()).limit(200).all()
        matched_ids.update(r.id for r in rows)
        per_role.append({"role": role, "count": len(rows)})

    sample = []
    if matched_ids:
        sample = (
            q.filter(JobPosting.id.in_(matched_ids))
            .order_by(JobPosting.first_seen_at.desc())
            .limit(limit)
            .all()
        )
    return {
        "total": total,
        "matching_roles": len(matched_ids),
        "per_role": per_role,
        "sample": [
            {"title": p.title, "company_name": p.company_name, "location": p.location}
            for p in sample
        ],
    }
