"""
Copertura delle skill del candidato rispetto a un annuncio, senza LLM.

Flusso:
    skills = extract_skills(requirements_text)   # {"required": [...], "nice": [...]}
    result = compute_coverage(user_skills, requirements_text)
    if passes_threshold(result):
        ...
"""
import re

from app.services.matcher import SKILL_SYNONYMS

COVERAGE_THRESHOLD = 0.6

# ---------------------------------------------------------------------------
# Dizionario esteso (~100 skill canoniche, con sinonimi tedeschi e italiani)
# SKILL_SYNONYMS di matcher.py viene usato come base; "cloud" e "git" sono
# ridefiniti: i provider cloud diventano skill autonome per maggiore granularità.
# ---------------------------------------------------------------------------
EXTENDED_SKILL_SYNONYMS: dict[str, list[str]] = {
    **SKILL_SYNONYMS,

    # --- Override ---
    "cloud":           ["cloud", "cloud computing"],
    "git":             ["git", "github", "gitlab", "bitbucket", "version control"],
    # "cv" rimosso: matchava "Send your CV" come falso positivo
    "computer vision": ["computer vision", "image processing", "opencv"],
    # "autonomous" rimosso: matchava "Our company is autonomous and independent"
    "robotics":        ["robotics", "robot"],

    # --- Linguaggi ---
    "typescript":  ["typescript", "ts"],
    "vue":         ["vue", "vuejs"],
    "kotlin":      ["kotlin"],
    "swift":       ["swift"],
    "golang":      ["golang", "go language"],
    "rust":        ["rust"],
    "scala":       ["scala"],
    "php":         ["php"],
    "ruby":        ["ruby", "rails", "ruby on rails"],
    "c++":         ["c++", "cpp"],
    "c#":          ["c#", "csharp", "c sharp"],
    "r":           ["r programming", "rstudio", "tidyverse"],
    "flutter":     ["flutter", "dart"],

    # --- Web / framework ---
    "django":      ["django"],
    "flask":       ["flask"],
    "fastapi":     ["fastapi"],
    "spring":      ["spring", "spring boot"],
    "html":        ["html", "html5"],
    "css":         ["css", "scss", "sass"],
    "graphql":     ["graphql"],
    "rest api":    ["rest", "restful", "rest api", "rest apis"],

    # --- Data & Big Data ---
    "spark":       ["spark", "apache spark", "pyspark"],
    "hadoop":      ["hadoop", "hdfs", "hive"],
    "kafka":       ["kafka", "apache kafka"],
    "pandas":      ["pandas"],
    "numpy":       ["numpy"],
    "etl":         ["etl", "data pipeline", "data pipelines", "etl pipeline", "etl pipelines"],
    "dbt":         ["dbt"],
    "airflow":     ["airflow", "apache airflow"],

    # --- Cloud provider & DevOps ---
    "aws":         ["aws", "amazon web services"],
    "azure":       ["azure", "microsoft azure"],
    "gcp":         ["gcp", "google cloud", "bigquery"],
    "terraform":   ["terraform"],
    "ansible":     ["ansible"],
    "linux":       ["linux", "unix", "bash", "shell scripting"],
    "jenkins":     ["jenkins"],
    "ci/cd":       ["cicd", "ci cd", "continuous integration"],
    "prometheus":  ["prometheus", "grafana"],
    "jupyter":     ["jupyter", "jupyter notebook", "colab"],

    # --- ML / AI ---
    "scikit-learn": ["scikit-learn", "sklearn"],
    "tensorflow":   ["tensorflow"],
    "pytorch":      ["pytorch"],
    "nlp":          ["nlp", "natural language processing", "text mining"],
    "llm":          ["llm", "large language model", "gpt", "openai"],
    "mlflow":       ["mlflow"],
    "langchain":    ["langchain"],

    # --- Database ---
    "postgresql":   ["postgresql", "postgres"],
    "mongodb":      ["mongodb", "nosql"],
    "redis":        ["redis"],
    "elasticsearch":["elasticsearch"],
    "snowflake":    ["snowflake"],
    "databricks":   ["databricks"],
    "oracle":       ["oracle"],

    # --- BI / Analytics ---
    "tableau":     ["tableau"],
    "looker":      ["looker", "looker studio"],
    "qlik":        ["qlik", "qlikview"],

    # --- Metodologie & Strumenti ---
    "jira":        ["jira", "confluence"],
    "uml":         ["uml"],
    "bpmn":        ["bpmn"],
    "postman":     ["postman"],
    "selenium":    ["selenium"],
    "figma":       ["figma"],

    # --- Sicurezza ---
    "cybersecurity": ["cybersecurity", "information security", "penetration testing", "oauth"],

    # --- Architettura ---
    "microservices": ["microservices", "service mesh", "event driven"],

    # --- ERP / Business ---
    "salesforce":   ["salesforce", "apex"],

    # --- Statistiche ---
    "ab testing":   ["ab testing", "a/b testing", "experimentation"],

    # --- Mobile ---
    "ios":          ["ios", "xcode"],
    "android":      ["android"],

    # --- Competenze "di mestiere" (non strumenti): servono soprattutto per
    #     gli annunci in tedesco e in italiano, che le nominano più dei tool ---
    "data analysis": [
        "data analysis", "data analyses",
        "datenanalyse", "datenanalysen", "datenauswertung", "datenauswertungen",
        "analisi dei dati", "analisi dati", "analisi di dati",
    ],
    "database": [
        "database", "databases", "relational database",
        "datenbank", "datenbanken", "datenbanksysteme", "datenbanksystemen",
        "datenmodell", "datenmodelle", "datenmodellen", "datenmodellierung",
        "banca dati", "banche dati", "base di dati", "basi di dati",
    ],
    "requirements engineering": [
        "requirements engineering", "requirements analysis", "requirements management",
        "requirements gathering",
        "anforderungsanalyse", "anforderungsanalysen", "anforderungsmanagement",
        "anforderungserhebung", "anforderungsaufnahme",
        "analisi dei requisiti", "raccolta dei requisiti", "raccolta requisiti",
    ],
    "project management": [
        "project management", "projektmanagement", "projektleitung",
        "projektmanagementmethoden", "projektarbeit",
        "gestione progetti", "gestione di progetti", "gestione dei progetti",
    ],
    "programming": [
        "programming", "software development",
        "programmierung", "programmierkenntnisse", "programmiersprache",
        "programmiersprachen", "programmiererfahrung", "softwareentwicklung",
        "programmazione", "sviluppo software",
    ],
    "reporting": [
        "reporting", "reportings", "berichtswesen", "berichterstattung",
        "reportistica",
    ],
    "data visualization": [
        "data visualization", "data visualisation", "dashboards", "dashboard",
        "datenvisualisierung", "visualizzazione dei dati", "visualizzazione dati",
    ],
    "business intelligence": ["business intelligence", "bi tools", "bi-tools"],
    "process management": [
        "process management", "business process management", "process modeling",
        "process modelling", "process mining",
        "prozessmanagement", "prozessmodellierung", "prozessoptimierung",
        "prozessanalyse", "geschäftsprozesse", "geschäftsprozessen",
        "processi aziendali", "analisi dei processi",
    ],
    "ms office": ["ms office", "ms-office", "microsoft office", "office 365", "m365"],
    "erp": ["erp", "erp-system", "erp-systeme", "erp-systemen"],

    # --- Skill di base con sinonimi tedeschi e italiani. Le prime quattro
    #     ridefiniscono per intero le voci ereditate da SKILL_SYNONYMS ---
    "machine learning": [
        "machine learning", "ml", "ai", "artificial intelligence",
        "maschinelles lernen", "maschinellen lernens", "maschinellem lernen",
        "maschinelle lernen", "künstliche intelligenz", "künstlicher intelligenz",
        "künstlichen intelligenz", "ki",
        "apprendimento automatico", "intelligenza artificiale",
    ],
    "data science": [
        "data science", "data analytics", "big data", "datenwissenschaft",
        "scienza dei dati",
    ],
    "python": ["python", "py", "pythonkenntnisse"],
    "sql": ["sql", "mysql", "postgresql", "sqlkenntnisse"],
    "excel": [
        "excel", "vba", "microsoft excel", "ms excel", "ms-excel",
        "excelkenntnisse", "tabellenkalkulation",
    ],
    "sap": ["sap", "s/4hana", "s4hana", "sapkenntnisse"],
    "power bi": ["power bi", "powerbi", "power-bi"],
    "agile": [
        "agile", "scrum", "kanban", "agil", "agilen", "agiler", "agiles",
        "agilem", "agilität", "metodologie agili", "metodi agili",
    ],
    "statistics": [
        "statistics", "statistical analysis", "probability",
        "statistik", "statistische", "statistischen", "statistica", "statistiche",
    ],
}

# ---------------------------------------------------------------------------
# Marcatori "gradito / nice to have"
#
# Un marcatore NON rende gradito tutto il testo che lo segue: vale solo
#   - per la sezione che apre, se sta in un titolo ("Nice to have:",
#     "PREFERRED QUALIFICATIONS", "Wünschenswerte Qualifikationen:");
#   - per la frase in cui compare ("Tableau is a plus.");
#   - per quello che lo segue nella frase, nel caso di "ideally" e simili
#     ("ML in production, ideally with Kafka" → ML richiesta, Kafka gradita).
# Prima bastava un "Ideally, you bring:" in cima ai requisiti per far finire
# tra le gradite tutte le skill dell'annuncio.
# ---------------------------------------------------------------------------
_NICE_RE = re.compile(
    r"nice[\s\-]to[\s\-]haves?|good\s+to\s+have|preferred|desirable|desired"
    r"|(?:is|are|as|would\s+be)\s+a\s+(?:strong\s+|big\s+|definite\s+)?plus"
    r"|bonus(?:\s+points?|\s+skills?)?|optional\s+skills?|pluspunkt\w*"
    r"|gradit[oaie]\b|titolo\s+preferenziale|costituisc\w+\s+un\s+plus"
    r"|von\s+vorteil|wünschenswert|vorteilhaft",
    re.IGNORECASE,
)
# Valgono solo da lì alla fine della frase.
_NICE_TAIL_RE = re.compile(
    r"\b(?:ideally|idealerweise|preferably|vorzugsweise|preferibilmente|optimalerweise)\b",
    re.IGNORECASE,
)
_BULLET_RE = re.compile(r"^\s*(?:[-–—•*·▪●◦]|\d+[.)])\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;!?])\s+")
_HEADING_MAX_LEN = 80
_HEADING_MAX_WORDS = 7


def _is_heading(line: str) -> bool:
    """Riga-titolo di sezione: corta, senza punto elenco, che finisce con
    i due punti oppure non è una frase ("WHAT WE OFFER", "Dein Profil")."""
    stripped = line.strip()
    if not stripped or len(stripped) > _HEADING_MAX_LEN or _BULLET_RE.match(line):
        return False
    if stripped.endswith(":"):
        return True
    if stripped[-1] in ".!?;,":
        return False
    return stripped.isupper() or len(stripped.split()) <= _HEADING_MAX_WORDS


def _split_required_nice(text: str) -> tuple[str, str]:
    """Divide il testo dell'annuncio in (parte richiesta, parte gradita)."""
    required: list[str] = []
    nice: list[str] = []
    in_nice_section = False

    for line in text.splitlines():
        if _is_heading(line):
            # ogni titolo chiude la sezione precedente; apre una sezione
            # "gradite" solo se contiene un marcatore
            in_nice_section = bool(_NICE_RE.search(line))
            if not in_nice_section:
                required.append(line)
            continue
        if in_nice_section:
            nice.append(line)
            continue

        sentences = _SENTENCE_SPLIT_RE.split(line)
        for i, sentence in enumerate(sentences):
            m = _NICE_RE.search(sentence)
            if m and sentence[m.end():].lstrip().startswith(":"):
                # "Nice to have: X. Y." dentro una riga: gradito fino a fine riga
                required.append(sentence[: m.start()])
                nice.append(sentence[m.start():])
                nice.extend(sentences[i + 1:])
                break
            if m:
                nice.append(sentence)
                continue
            tail = _NICE_TAIL_RE.search(sentence)
            if tail:
                required.append(sentence[: tail.start()])
                nice.append(sentence[tail.start():])
            else:
                required.append(sentence)

    return "\n".join(required), "\n".join(nice)

# ---------------------------------------------------------------------------
# Costruzione delle regex per singola skill (gestisce caratteri speciali)
# ---------------------------------------------------------------------------

def _make_skill_re(syns: list[str]) -> re.Pattern:
    r"""Compila una regex con \b word boundaries per ogni sinonimo.
    Per sinonimi che iniziano/finiscono con caratteri non-word (c#, .net...)
    usa lookaround (?<!\w) / (?!\w) al posto di \b.
    """
    parts = []
    for syn in sorted({s.lower() for s in syns if s}, key=len, reverse=True):
        escaped = re.escape(syn)
        lb = r"\b" if syn[0].isalnum() or syn[0] == "_" else r"(?<!\w)"
        rb = r"\b" if syn[-1].isalnum() or syn[-1] == "_" else r"(?!\w)"
        parts.append(f"{lb}{escaped}{rb}")
    return re.compile("|".join(parts), re.IGNORECASE)


_SKILL_REGEXES: dict[str, re.Pattern] = {
    canonical: _make_skill_re(syns)
    for canonical, syns in EXTENDED_SKILL_SYNONYMS.items()
}

# ---------------------------------------------------------------------------
# Tabella inversa: sinonimo → nome canonico
# ---------------------------------------------------------------------------
_SYN_TO_CANONICAL: dict[str, str] = {}
for _canonical, _syns in EXTENDED_SKILL_SYNONYMS.items():
    _SYN_TO_CANONICAL[_canonical.lower()] = _canonical
    for _syn in _syns:
        _SYN_TO_CANONICAL[_syn.lower()] = _canonical


def _normalize_skill(skill: str) -> str:
    return _SYN_TO_CANONICAL.get(skill.lower().strip(), skill.lower().strip())


# Skill generiche che il candidato possiede di fatto se ne ha una specifica:
# chi sa Python "sa programmare", chi sa SQL "conosce i database". Senza
# questo, "Programmierung" o "Datenbanken" in un annuncio risulterebbero
# mancanti a chi nel profilo ha scritto solo i linguaggi.
_IMPLIED_BY: dict[str, frozenset[str]] = {
    "programming": frozenset({
        "python", "java", "javascript", "typescript", "kotlin", "swift", "golang",
        "rust", "scala", "php", "ruby", "c++", "c#", "r",
    }),
    "database": frozenset({
        "sql", "postgresql", "mongodb", "oracle", "redis", "snowflake",
    }),
}


def _user_canonical(user_skills: list[str]) -> set[str]:
    canonical = {_normalize_skill(s) for s in user_skills if s}
    implied = {skill for skill, sources in _IMPLIED_BY.items() if canonical & sources}
    return canonical | implied


# ---------------------------------------------------------------------------
# Funzioni pubbliche
# ---------------------------------------------------------------------------

def _find_skills(text: str) -> set[str]:
    return {c for c, rx in _SKILL_REGEXES.items() if rx.search(text)}


def extract_skills(text: str) -> dict[str, list[str]]:
    """Trova le skill tecniche nel testo dell'annuncio.

    Separa le skill richieste da quelle gradite cercando marcatori come
    "nice to have", "gradito", "von Vorteil" ecc. (vedi _split_required_nice).
    Una skill che compare sia tra le richieste sia tra le gradite è richiesta.
    Ritorna {"required": [...], "nice": [...]}.
    """
    required_text, nice_text = _split_required_nice(text or "")

    required = _find_skills(required_text)
    nice = _find_skills(nice_text) - required
    return {"required": sorted(required), "nice": sorted(nice)}


def compute_coverage(user_skills: list[str], requirements_text: str) -> dict:
    """Calcola la percentuale di copertura delle skill richieste dall'annuncio.

    Le skill richieste pesano il doppio di quelle gradite.
    Se nell'annuncio non si trova nessuna skill riconoscibile, ritorna
    percentage=None (meglio mostrare l'annuncio che escluderlo per errore).

    Ritorna:
        percentage   – float in [0, 1] o None
        matched      – skill coperte dall'utente
        missing_required – skill richieste mancanti
        missing_nice     – skill gradite mancanti
    """
    skills = extract_skills(requirements_text)
    required = set(skills["required"])
    nice = set(skills["nice"])

    if not required and not nice:
        return {"percentage": None, "matched": [], "missing_required": [], "missing_nice": []}

    user_canonical = _user_canonical(user_skills)

    matched_req = required & user_canonical
    matched_nice = nice & user_canonical
    matched = sorted(matched_req | matched_nice)
    missing_required = sorted(required - matched_req)
    missing_nice = sorted(nice - matched_nice)

    total_weight = len(required) * 2 + len(nice)
    matched_weight = len(matched_req) * 2 + len(matched_nice)
    percentage = round(matched_weight / total_weight, 3) if total_weight else None

    return {
        "percentage": percentage,
        "matched": matched,
        "missing_required": missing_required,
        "missing_nice": missing_nice,
    }


def passes_threshold(result: dict) -> bool:
    """True se l'annuncio supera COVERAGE_THRESHOLD, o se percentage è None
    (nessuna skill trovata nel testo → non escludiamo per errore).
    """
    pct = result.get("percentage")
    return pct is None or pct >= COVERAGE_THRESHOLD
