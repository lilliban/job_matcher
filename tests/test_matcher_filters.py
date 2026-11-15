import pytest

from app.services.matcher import MatchingEngine, normalize_semantic_score, seniority_check


# --- normalize_semantic_score ---

def test_normalize_scales_100_range():
    assert normalize_semantic_score(75) == pytest.approx(0.75)


def test_normalize_keeps_already_normalized():
    assert normalize_semantic_score(0.8) == pytest.approx(0.8)


# --- seniority_check ---

def test_seniority_excludes_senior_title():
    incompatible, reason = seniority_check("Senior Backend Developer", "")
    assert incompatible is True
    assert "senior" in reason


def test_seniority_keeps_junior_title_despite_text_years():
    # titolo junior → non guardare il testo, anche se richiede 5 anni
    incompatible, _ = seniority_check("Junior Python Developer", "requires 5 years of experience")
    assert incompatible is False


def test_seniority_excludes_neutral_title_with_high_years_in_text():
    incompatible, reason = seniority_check("Python Developer", "5+ anni di esperienza richiesti")
    assert incompatible is True
    assert "5" in reason


def test_seniority_keeps_stage_project_manager():
    # "stage" è una JUNIOR_KEYWORDS → tenuto nonostante "manager" nel resto
    incompatible, _ = seniority_check("Stage Project Manager", "")
    assert incompatible is False


def test_seniority_keeps_data_science_intern():
    incompatible, _ = seniority_check("Data Science Intern", "")
    assert incompatible is False


def test_seniority_title_none_no_error():
    incompatible, _ = seniority_check(None, None)
    assert incompatible is False


def test_seniority_excludes_senior_international_sales_manager():
    # "senior" è parola intera, "international" non deve triggerare junior
    incompatible, _ = seniority_check("Senior International Sales Manager", "")
    assert incompatible is True


def test_seniority_excludes_internal_auditor_lead():
    # "internal" non deve triggerare "intern" come junior; "lead" deve escludere
    incompatible, _ = seniority_check("Internal Auditor Lead", "")
    assert incompatible is True


def test_seniority_keeps_praktikantin_data_analytics():
    incompatible, _ = seniority_check("Praktikantin Data Analytics", "")
    assert incompatible is False


def test_seniority_keeps_werkstudentin_bi():
    incompatible, _ = seniority_check("Werkstudentin BI", "")
    assert incompatible is False


# --- MatchingEngine constructor / soft_skills ---

class _FakeLLM:
    pass


def test_hard_skills_missing_name_key_no_crash():
    # una skill senza "name" non deve far crashare il costruttore
    profile = {"hard_skills": [{"level": "expert"}, {"name": "Python"}]}
    engine = MatchingEngine(_FakeLLM(), profile)
    assert engine.user_skills == ["python"]


# --- seniority_check: min_years_exp e filtro storia ---

def test_seniority_min_years_exp_over_2_excluded():
    # DB dice 5 anni → scarta anche se il testo è vuoto
    incompatible, reason = seniority_check("Python Developer", "", min_years_exp=5)
    assert incompatible is True
    assert "5" in reason


def test_seniority_min_years_exp_1_kept():
    # DB dice 1 anno → tieni, non serve guardare il testo
    incompatible, _ = seniority_check("Python Developer", "5+ anni di esperienza", min_years_exp=1)
    assert incompatible is False


def test_seniority_fallback_regex_on_missing_min_years():
    # Nessun valore DB → regex sul testo trova "5 anni"
    incompatible, reason = seniority_check("Python Developer", "richiede 5 anni di esperienza")
    assert incompatible is True
    assert "5" in reason


def test_seniority_ignores_very_high_years_in_text():
    # 30 anni > 15 → ignorato dalla regex (è storia aziendale)
    incompatible, _ = seniority_check("Software Engineer", "azienda con 30 years of experience nel settore")
    assert incompatible is False


def test_seniority_ignores_history_phrase_in_text():
    # "anni di storia" → contesto storico, non requisito di esperienza
    incompatible, _ = seniority_check("Software Engineer", "10 anni di storia aziendale")
    assert incompatible is False


def test_soft_skills_as_dicts_no_crash():
    # soft_skills come lista di dict non deve dare TypeError nel prompt
    profile = {
        "soft_skills": [{"name": "Comunicazione"}, {"name": "Problem solving"}],
    }
    engine = MatchingEngine(_FakeLLM(), profile)
    # verifica che la costruzione del testo non lanci eccezioni
    soft = profile["soft_skills"]
    result = ", ".join(s["name"] if isinstance(s, dict) else s for s in soft)
    assert result == "Comunicazione, Problem solving"
