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
# Dizionario esteso (~91 skill canoniche)
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
    "rest api":    ["rest", "restful", "rest api"],

    # --- Data & Big Data ---
    "spark":       ["spark", "apache spark", "pyspark"],
    "hadoop":      ["hadoop", "hdfs", "hive"],
    "kafka":       ["kafka", "apache kafka"],
    "pandas":      ["pandas"],
    "numpy":       ["numpy"],
    "etl":         ["etl", "data pipeline"],
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
    "power bi":    ["power bi", "powerbi"],
    "tableau":     ["tableau"],
    "excel":       ["excel", "vba", "microsoft excel"],
    "looker":      ["looker"],
    "qlik":        ["qlik", "qlikview"],

    # --- Metodologie & Strumenti ---
    "jira":        ["jira", "confluence"],
    "agile":       ["agile", "scrum", "kanban"],
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
    "sap":          ["sap", "s/4hana"],
    "salesforce":   ["salesforce", "apex"],

    # --- Statistiche ---
    "statistics":   ["statistics", "statistical analysis", "probability"],
    "ab testing":   ["ab testing", "a/b testing", "experimentation"],

    # --- Mobile ---
    "ios":          ["ios", "xcode"],
    "android":      ["android"],
}

# ---------------------------------------------------------------------------
# Regex per il rilevamento dei marcatori "gradito / nice to have"
# ---------------------------------------------------------------------------
_NICE_RE = re.compile(
    r"nice[\s\-]to[\s\-]have|preferred|is\s+a\s+plus|gradito|von\s+vorteil"
    r"|wünschenswert|desirable|ideally|bonus\s+skill|optional\s+skill|good\s+to\s+have",
    re.IGNORECASE,
)

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


# ---------------------------------------------------------------------------
# Funzioni pubbliche
# ---------------------------------------------------------------------------

def _find_skills(text: str) -> set[str]:
    return {c for c, rx in _SKILL_REGEXES.items() if rx.search(text)}


def extract_skills(text: str) -> dict[str, list[str]]:
    """Trova le skill tecniche nel testo dell'annuncio.

    Separa le skill richieste da quelle gradite cercando marcatori come
    "nice to have", "gradito", "von Vorteil" ecc.
    Ritorna {"required": [...], "nice": [...]}.
    """
    text = text or ""
    m = _NICE_RE.search(text)
    if m:
        required_text = text[: m.start()]
        nice_text = text[m.start() :]
    else:
        required_text = text
        nice_text = ""

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

    user_canonical = {_normalize_skill(s) for s in user_skills if s}

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
