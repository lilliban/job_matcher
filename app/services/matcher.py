"""
MatchingEngine — RF4.1, RF4.2

Score ibrido (mitigazione R07):
  - keyword_score: quante skill richieste compaiono nel testo dell'annuncio.
                   Veloce, gratuito, usato come pre-filtro.
  - semantic_score: valutazione LLM del fit reale profilo↔annuncio.
                    Costoso, chiamato solo se il pre-filtro passa.

Lo score finale è la media pesata dei due (config: KEYWORD_WEIGHT,
SEMANTIC_WEIGHT). Il dettaglio è sempre esposto all'utente perché possa
capire il perché del punteggio.
"""
import json
import logging
import re
from typing import Iterable

from app.core.config import KEYWORD_WEIGHT, SEMANTIC_WEIGHT
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

# se il keyword score è sotto questa soglia non chiamiamo neanche l'LLM
PREFILTER_MIN = 0.0

SKILL_SYNONYMS = {
    "python": ["python", "py"],
    "machine learning": ["machine learning", "ml", "ai"],
    "data science": ["data science", "data analytics", "big data"],
    "deep learning": ["deep learning", "dl", "neural networks"],
    "computer vision": ["computer vision", "cv", "image processing"],
    "robotics": ["robotics", "robot", "autonomous"],
    "sql": ["sql", "mysql", "postgresql"],
    "java": ["java", "j2ee"],
    "javascript": ["javascript", "js", "node"],
    "react": ["react", "reactjs"],
    "angular": ["angular", "angularjs"],
    "docker": ["docker", "container"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git", "github", "gitlab"],
    "cloud": ["cloud", "aws", "azure", "gcp"],
}
    

class MatchingEngine:
    def __init__(self, llm: LLMGateway, user_profile: dict | None = None):
        self.llm = llm
        self.user_profile = user_profile or {}
        self.user_skills = [s["name"].lower() for s in self.user_profile.get("hard_skills", [])]
        self.user_languages = self.user_profile.get("languages", [])
        self.user_years_exp = self.user_profile.get("years_experience_total", 0)
        self.work_mode_pref = self.user_profile.get("work_mode_pref")
        self.min_salary = self.user_profile.get("min_salary", 0)

    # -----------------------------------------------------------------
    def filter_incompatible(self, listing: dict) -> tuple[bool, str]:
        """Ritorna (is_incompatible, motivo)."""
        requirements = (listing.get("requirements_raw") or listing.get("description") or "").lower()
        
        # 1. Controlla lingue richieste
        for lang in self.user_languages:
            lang_name = lang.get("language", "")
            lang_level = lang.get("level", "")
            # Se l'annuncio richiede fluentemente una lingua che l'utente parla a basso livello
            if lang_level in ["A1", "A2"]:
                if f"fluent {lang_name}" in requirements or f"fluently {lang_name}" in requirements:
                    return True, f"richiede {lang_name} fluente (tu hai {lang_level})"
        
        # 2. Controlla anni esperienza
        years_pattern = re.findall(r'(\d+)\s*\+?\s*(?:years|anni|jahre|ans)', requirements)
        for y in years_pattern:
            if int(y) > self.user_years_exp + 2:  # tolleranza 2 anni
                return True, f"richiede {y}+ anni di esperienza (tu hai {self.user_years_exp})"
        
        # 3. Controlla work mode
        if self.work_mode_pref == "remote":
            if "on-site" in requirements or "onsite" in requirements:
                return True, "richiede presenza in ufficio"
        
        return False, ""

    # -----------------------------------------------------------------
    
    # app/services/matcher.py - dentro la classe MatchingEngine

    def compute_keyword_score(
        self, user_skills: Iterable[str], requirements_raw: str
    ) -> tuple[float, list[str], list[str]]:
        """Confronta le skill dell'UTENTE con il testo dell'annuncio.
        Ritorna (score, matched, missing_from_user_perspective).
        Usa sinonimi per migliorare il matching."""
        text = (requirements_raw or "").lower()
        skills = [s for s in user_skills if s]
        if not skills or not text:
            return 0.0, [], []

        matched = []
        for skill in skills:
            skill_lower = skill.lower()
            
            # 1. Cerca il termine esatto
            if skill_lower in text:
                matched.append(skill)
                continue
            
            # 2. Cerca sinonimi
            synonyms = SKILL_SYNONYMS.get(skill_lower, [])
            found = False
            for syn in synonyms:
                if syn.lower() in text:
                    matched.append(skill)
                    found = True
                    break
            
            # 3. Se non trovato, log per debug
            if not found:
                logger.debug(f"Skill non trovata: {skill}")

        score = len(matched) / len(skills) if skills else 0.0
        logger.info(f"🔍 Keyword score: {score:.3f} ({len(matched)}/{len(skills)} skill trovate)")
        return round(score, 3), matched, []
    
    

    def compute_requirement_coverage(
        self, user_skills: Iterable[str], required_skills: Iterable[str]
    ) -> tuple[float, list[str], list[str]]:
        """Quante delle skill RICHIESTE dal ruolo l'utente possiede."""
        user_set = {s.lower().strip() for s in user_skills if s}
        required = [s for s in required_skills if s]
        if not required:
            return 0.0, [], []

        matched = [s for s in required if s.lower().strip() in user_set]
        missing = [s for s in required if s.lower().strip() not in user_set]
        score = len(matched) / len(required)
        return round(score, 3), matched, missing

    # -----------------------------------------------------------------
    async def compute_score(
        self,
        user_skills: list[str],
        required_skills: list[str],
        listing: dict,
        user_profile: dict | None = None,
    ) -> dict:
        """Calcolo completo dello score con gap analysis."""
        requirements = listing.get("requirements_raw") or listing.get("description") or ""

        kw_score, kw_matched, _ = self.compute_keyword_score(user_skills, requirements)
        cov_score, cov_matched, cov_missing = self.compute_requirement_coverage(
            user_skills, required_skills
        )
        # il keyword score combina presenza nel testo + copertura requisiti
        keyword_score = round((kw_score + cov_score) / 2, 3) if required_skills else kw_score

        semantic_score = 0.0
        semantic_evaluated = False
        gap_analysis = None
        llm_matched: list[str] = []
        llm_missing: list[str] = []

        sem = await self._semantic_evaluation(user_skills, listing, user_profile)
        if sem:
            semantic_evaluated = True
            semantic_score = sem.get("score", 0.0)
            gap_analysis = sem.get("gap_analysis")
            llm_matched = sem.get("matched_skills") or []
            llm_missing = sem.get("missing_skills") or []
        else:
            gap_analysis = "Errore nella valutazione semantica"
            semantic_score = 0.0

        final = round(
            keyword_score * KEYWORD_WEIGHT + semantic_score * SEMANTIC_WEIGHT, 3
        ) if semantic_evaluated else round(keyword_score * 0.7, 3)

        matched = sorted(set(kw_matched + cov_matched + llm_matched))
        missing = sorted(set(cov_missing + llm_missing))

        return {
            "score": final,
            "keyword_score": keyword_score,
            "semantic_score": semantic_score,
            "matched_skills": json.dumps(matched, ensure_ascii=False),
            "missing_skills": json.dumps(missing, ensure_ascii=False),
            "gap_analysis": gap_analysis,
        }

    # -----------------------------------------------------------------
    async def _semantic_evaluation(
        self, user_skills: list[str], listing: dict, user_profile: dict | None
    ) -> dict | None:
        """Valutazione semantica con Gemini."""
        
        profile_lines = ["=== PROFILO COMPLETO CANDIDATO ==="]
        
        if user_profile:
            # Anagrafica
            if user_profile.get("name"):
                profile_lines.append(f"Nome: {user_profile['name']}")
            if user_profile.get("email"):
                profile_lines.append(f"Email: {user_profile['email']}")
            if user_profile.get("phone"):
                profile_lines.append(f"Telefono: {user_profile['phone']}")
            if user_profile.get("location"):
                profile_lines.append(f"Località: {user_profile['location']}")
            if user_profile.get("bio"):
                profile_lines.append(f"Bio: {user_profile['bio']}")
            
            # HARD SKILLS dettagliate
            if user_profile.get("hard_skills"):
                profile_lines.append("\nCOMPETENZE TECNICHE:")
                level_map = {"beginner": "Base", "intermediate": "Intermedio", "expert": "Avanzato"}
                for s in user_profile["hard_skills"]:
                    profile_lines.append(
                        f"  - {s.get('name')}: {level_map.get(s.get('level'), s.get('level', 'n/d'))} "
                        f"({s.get('years_exp', 0)} anni)"
                    )
            
            # SOFT SKILLS
            if user_profile.get("soft_skills"):
                profile_lines.append(f"\nSOFT SKILLS: {', '.join(user_profile['soft_skills'])}")
            
            # LINGUE
            if user_profile.get("languages"):
                profile_lines.append("\nLINGUE:")
                for lang in user_profile["languages"]:
                    profile_lines.append(f"  - {lang.get('language')}: {lang.get('level')}")
            
            # ESPERIENZE
            if user_profile.get("experiences"):
                profile_lines.append("\nESPERIENZE LAVORATIVE:")
                for exp in user_profile["experiences"][:5]:
                    periodo = f"{exp.get('start_date', '?')} → {exp.get('end_date') or 'oggi'}"
                    profile_lines.append(f"  - {exp.get('role')} presso {exp.get('company')} ({periodo})")
                    if exp.get("description"):
                        profile_lines.append(f"    {exp.get('description')[:200]}")
                    if exp.get("skills_used"):
                        profile_lines.append(f"    Tecnologie: {exp.get('skills_used')}")
            
            # FORMAZIONE
            if user_profile.get("education"):
                profile_lines.append("\nFORMAZIONE:")
                for edu in user_profile["education"][:3]:
                    profile_lines.append(
                        f"  - {edu.get('degree', 'Titolo')} in {edu.get('field', '')} "
                        f"presso {edu.get('institution', '')} ({edu.get('year', '')})"
                    )
        
        # Annuncio
        profile_lines.append("\n=== ANNUNCIO DI LAVORO ===")
        profile_lines.append(f"Ruolo: {listing.get('title')}")
        profile_lines.append(f"Azienda: {listing.get('company_name')}")
        if listing.get("location"):
            profile_lines.append(f"Sede: {listing.get('location')}")
        if listing.get("contract_type"):
            profile_lines.append(f"Contratto: {listing.get('contract_type')}")
        
        profile_lines.append("\nREQUISITI:")
        profile_lines.append((listing.get("requirements_raw") or listing.get("description") or "")[:3000])
        
        full_prompt = "\n".join(profile_lines) + """

    === VALUTAZIONE ===

    Valuta la compatibilità su 4 dimensioni (0-100):

    1. COMPETENZE TECNICHE (40% del peso)
    - Quante competenze del candidato sono menzionate nell'annuncio?
    - Quante competenze richieste ha il candidato?
    - Considera competenze simili (es. "Data Science" ≈ "Machine Learning")
    - Considera il livello di esperienza richiesto vs posseduto

    2. ESPERIENZA LAVORATIVA (30% del peso)
    - Gli anni di esperienza corrispondono?
    - I ruoli precedenti sono rilevanti?
    - Le responsabilità descritte sono simili?

    3. FORMAZIONE (20% del peso)
    - Il titolo di studio è rilevante?
    - L'ambito di studi è allineato?

    4. SOFT SKILLS E LINGUE (10% del peso)
    - Le soft skills del candidato corrispondono?
    - Le lingue richieste sono parlate?

    Rispondi SOLO con un oggetto JSON:
    {
        "score": 75,
        "matched_skills": ["Python", "Machine Learning", "SQL"],
        "missing_skills": ["Java", "Docker"],
        "gap_analysis": "Testo in italiano che spiega cosa manca e come colmarlo"
    }"""

        SYSTEM_PROMPT = """
    Sei un esperto recruiter specializzato in tecnologia e data science.
    Valuti la compatibilità tra un candidato e un annuncio di lavoro.

    REGOLE:
    1. Sii obiettivo e basati solo sui dati forniti
    2. Non cercare solo parole chiave esatte, considera il contesto
    3. Riconosci competenze simili (es. "Data Science" ≈ "Machine Learning")
    4. Valuta sia competenze tecniche che soft skills
    5. Considera il livello di esperienza (junior/mid/senior)
    6. Se il candidato ha >70% delle competenze richieste, lo score deve essere >70
    7. Se il candidato ha <30% delle competenze richieste, lo score deve essere <30
    """

        data = await self.llm.complete_json(full_prompt, default=None, system_prompt=SYSTEM_PROMPT)
        if not isinstance(data, dict):
            return None

        try:
            score = float(data.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0

        return {
            "score": max(0.0, min(1.0, score)),
            "matched_skills": data.get("matched_skills") if isinstance(data.get("matched_skills"), list) else [],
            "missing_skills": data.get("missing_skills") if isinstance(data.get("missing_skills"), list) else [],
            "gap_analysis": data.get("gap_analysis"),
        }

    # -----------------------------------------------------------------
    # RF8.4 — suggerimento ruoli alternativi
    # -----------------------------------------------------------------
    async def suggest_alternative_roles(
        self, role_title: str, user_skills: list[str], limit: int = 3
    ) -> list[dict]:
        prompt = (
            f"Il candidato cerca lavoro come '{role_title}' e possiede queste competenze: "
            f"{', '.join(user_skills) or 'non specificate'}.\n\n"
            f"Suggerisci {limit} ruoli ALTERNATIVI con competenze sovrapposte, "
            "dove il candidato avrebbe buone probabilità e dove il mercato offre più posizioni.\n\n"
            'Rispondi SOLO con un array JSON: '
            '[{"role": "...", "overlap": "quali skill si sovrappongono", "why": "perché conviene considerarlo"}]'
        )
        data = await self.llm.complete_json(prompt, default=[])
        return data if isinstance(data, list) else []