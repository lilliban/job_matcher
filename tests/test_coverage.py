import pytest

from app.services.coverage import (
    COVERAGE_THRESHOLD,
    compute_coverage,
    extract_skills,
    passes_threshold,
)


# ---------------------------------------------------------------------------
# extract_skills
# ---------------------------------------------------------------------------

def test_extract_skills_separates_required_and_nice():
    text = "Required: Python, SQL, Docker. Nice to have: Kubernetes, Spark."
    result = extract_skills(text)
    assert "python" in result["required"]
    assert "sql" in result["required"]
    assert "docker" in result["required"]
    assert "kubernetes" in result["nice"]
    assert "spark" in result["nice"]


def test_extract_skills_empty_text():
    assert extract_skills("") == {"required": [], "nice": []}
    assert extract_skills(None) == {"required": [], "nice": []}


def test_extract_skills_no_tech_skills():
    result = extract_skills("We are looking for a friendly and motivated team player.")
    assert result["required"] == []
    assert result["nice"] == []


def test_extract_skills_synonym_recognized():
    text = "Experience with ml and k8s required."
    result = extract_skills(text)
    assert "machine learning" in result["required"]
    assert "kubernetes" in result["required"]


def test_extract_skills_no_nice_marker_all_required():
    text = "Must know Python, React, Docker and Git."
    result = extract_skills(text)
    assert "python" in result["required"]
    assert "react" in result["required"]
    assert result["nice"] == []


# ---------------------------------------------------------------------------
# compute_coverage
# ---------------------------------------------------------------------------

def test_compute_coverage_full_match():
    user = ["python", "sql", "docker"]
    text = "Required: Python, SQL, Docker."
    result = compute_coverage(user, text)
    assert result["percentage"] == pytest.approx(1.0)
    assert result["missing_required"] == []
    assert result["missing_nice"] == []


def test_compute_coverage_partial_match():
    user = ["python"]
    text = "Required: Python, SQL, Docker."
    result = compute_coverage(user, text)
    # matched_req=1 (weight 2), total=3*2=6 → 2/6 ≈ 0.333
    assert result["percentage"] == pytest.approx(1 / 3, rel=0.01)
    assert "sql" in result["missing_required"]
    assert "docker" in result["missing_required"]
    assert "python" in result["matched"]


def test_compute_coverage_no_skills_in_text_returns_none():
    result = compute_coverage(["python"], "We are hiring a great communicator.")
    assert result["percentage"] is None
    assert result["matched"] == []


def test_compute_coverage_nice_weights_half_required():
    # Required: Python, SQL (total_weight=4). Nice: Docker (weight=1). Total=5.
    # User has Python (req, +2) + Docker (nice, +1) = 3/5 = 0.6
    user = ["python", "docker"]
    text = "Must have: Python, SQL. Nice to have: Docker."
    result = compute_coverage(user, text)
    assert result["percentage"] == pytest.approx(3 / 5)
    assert "sql" in result["missing_required"]
    assert result["missing_nice"] == []


def test_compute_coverage_synonym_user_skill():
    # utente ha "ml", annuncio dice "machine learning"
    result = compute_coverage(["ml"], "Experience with machine learning required.")
    assert result["percentage"] is not None
    assert "machine learning" in result["matched"]


def test_compute_coverage_zero_match():
    user = ["excel"]
    text = "Required: Python, Kubernetes, Spark."
    result = compute_coverage(user, text)
    assert result["percentage"] == pytest.approx(0.0)
    assert result["matched"] == []
    assert len(result["missing_required"]) == 3


# ---------------------------------------------------------------------------
# passes_threshold
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Falsi positivi — testi che NON devono trovare skill sbagliate
# ---------------------------------------------------------------------------

def test_cv_not_matched_as_computer_vision():
    result = extract_skills("Send your CV to our team.")
    assert "computer vision" not in result["required"]
    assert "computer vision" not in result["nice"]


def test_go_not_matched_as_golang():
    result = extract_skills("We go to market fast.")
    assert "golang" not in result["required"]
    assert "golang" not in result["nice"]


def test_rd_not_matched_as_r():
    result = extract_skills("R&D department.")
    assert "r" not in result["required"]
    assert "r" not in result["nice"]


def test_autonomous_not_matched_as_robotics():
    result = extract_skills("Our company is autonomous and independent.")
    assert "robotics" not in result["required"]
    assert "robotics" not in result["nice"]


# ---------------------------------------------------------------------------
# Veri positivi — testi che DEVONO trovare le skill corrette
# ---------------------------------------------------------------------------

def test_golang_matched():
    result = extract_skills("Experience with Golang.")
    assert "golang" in result["required"]


def test_cpp_and_csharp_matched():
    result = extract_skills("Knowledge of C++ and C#.")
    assert "c++" in result["required"]
    assert "c#" in result["required"]


def test_computer_vision_matched():
    result = extract_skills("Computer vision and OpenCV.")
    assert "computer vision" in result["required"]


def test_passes_threshold_keeps_none():
    assert passes_threshold({"percentage": None}) is True


def test_passes_threshold_above():
    assert passes_threshold({"percentage": 0.7}) is True
    assert passes_threshold({"percentage": COVERAGE_THRESHOLD}) is True


def test_passes_threshold_below():
    assert passes_threshold({"percentage": 0.4}) is False
    assert passes_threshold({"percentage": 0.0}) is False


# ---------------------------------------------------------------------------
# Sinonimi tedeschi e italiani
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, skill", [
    ("Erfahrung in der Datenanalyse", "data analysis"),
    ("Kenntnisse in Datenbanken", "database"),
    ("Du übernimmst die Anforderungsanalyse", "requirements engineering"),
    ("Erste Erfahrung im Projektmanagement", "project management"),
    ("Grundkenntnisse in der Programmierung", "programming"),
    ("Interesse an maschinellem Lernen", "machine learning"),
    ("Begeisterung für Künstliche Intelligenz", "machine learning"),
    ("Unterstützung im Berichtswesen", "reporting"),
    ("Aufbau des Reporting", "reporting"),
    ("Arbeiten nach Scrum", "agile"),
    ("Erfahrung mit agilen Methoden", "agile"),
    ("SAP-Kenntnisse", "sap"),
    ("Sehr gute Excel-Kenntnisse", "excel"),
    ("Gute Excelkenntnisse", "excel"),
    ("SQL-Kenntnisse", "sql"),
    ("Python-Kenntnisse", "python"),
    ("Erfahrung mit Power BI", "power bi"),
    ("Erfahrung mit Tableau", "tableau"),
    ("Esperienza in analisi dei dati", "data analysis"),
    ("Conoscenza delle basi di dati", "database"),
    ("Analisi dei requisiti con il cliente", "requirements engineering"),
    ("Gestione progetti", "project management"),
    ("Basi di programmazione", "programming"),
    ("Interesse per l'apprendimento automatico", "machine learning"),
    ("Produzione di reportistica", "reporting"),
])
def test_german_and_italian_synonyms(text, skill):
    assert skill in extract_skills(text)["required"]


def test_german_posting_gets_a_measured_coverage():
    text = (
        "Dein Profil\n"
        "- Studium der Wirtschaftsinformatik\n"
        "- Erfahrung in der Datenanalyse und mit Datenbanken\n"
        "- Sehr gute Excel-Kenntnisse, SQL von Vorteil\n"
    )
    result = compute_coverage(["Excel", "SQL"], text)
    assert result["percentage"] is not None
    assert "excel" in result["matched"]
    assert "data analysis" in result["missing_required"]


def test_specific_skill_implies_generic_one():
    # chi ha Python sa programmare, chi ha SQL conosce i database
    result = compute_coverage(["Python", "MySQL"], "Programmierung und Datenbanken")
    assert result["percentage"] == pytest.approx(1.0)
    assert result["matched"] == ["database", "programming"]
    # senza un linguaggio nel profilo, "programming" resta mancante
    assert compute_coverage(["Excel"], "Programmierung")["missing_required"] == ["programming"]


# ---------------------------------------------------------------------------
# Richieste vs gradite
# ---------------------------------------------------------------------------

def test_ml_required_is_not_nice_when_ideally_opens_the_requirements():
    # caso reale: "Ideally, you bring:" prima dell'elenco dei requisiti
    text = (
        "We are looking for engineers with GitHub contributions. Ideally, you bring:\n\n"
        " - Experience deploying and serving ML models in production.\n\n"
        " - Strong Python skills.\n"
    )
    result = extract_skills(text)
    assert "machine learning" in result["required"]
    assert "python" in result["required"]
    assert result["nice"] == []


def test_ml_in_requirements_and_in_nice_section_is_required():
    text = (
        "Requirements\n"
        "- Solid machine learning background\n"
        "Nice to have:\n"
        "- Machine learning in production, Kubernetes\n"
    )
    result = extract_skills(text)
    assert "machine learning" in result["required"]
    assert result["nice"] == ["kubernetes"]


def test_requirements_after_a_nice_section_are_required():
    text = (
        "Nice to have:\n"
        "- Kubernetes\n"
        "Requirements:\n"
        "- Machine learning and Python\n"
    )
    result = extract_skills(text)
    assert result["required"] == ["machine learning", "python"]
    assert result["nice"] == ["kubernetes"]


def test_inline_marker_only_affects_its_sentence():
    text = "- Python and SQL.\n- Tableau is a plus.\n- Machine learning for forecasting.\n"
    result = extract_skills(text)
    assert result["required"] == ["machine learning", "python", "sql"]
    assert result["nice"] == ["tableau"]


def test_ideally_only_affects_what_follows_in_the_sentence():
    text = "- Experience with machine learning pipelines, ideally with Kafka.\n- SQL\n"
    result = extract_skills(text)
    assert result["required"] == ["machine learning", "sql"]
    assert result["nice"] == ["kafka"]


def test_german_nice_section():
    text = (
        "Dein Profil\n"
        "- Erfahrung mit Python\n"
        "Wünschenswerte Qualifikationen:\n"
        "- Erfahrung mit Datenbanken\n"
        "Wir bieten\n"
        "- Arbeiten mit SAP\n"
    )
    result = extract_skills(text)
    assert result["required"] == ["python", "sap"]
    assert result["nice"] == ["database"]
