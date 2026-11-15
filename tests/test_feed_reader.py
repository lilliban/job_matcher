import sqlite3
from unittest.mock import patch

import pytest

from app.services.feed_reader import (
    ALLOWED_COUNTRIES,
    EUROPE_COUNTRIES,
    POSTING_COLUMNS,
    country_ok,
    download_feed,
    is_tech_role,
    load_postings,
    posting_kind,
    posting_region,
    prefilter,
    role_category,
)
from app.services.matcher import seniority_check


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path, rows: list[dict]):
    """Crea un mini-database con la tabella postings e le righe passate."""
    db = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db)
    cols_def = ", ".join(f"{c} TEXT" for c in POSTING_COLUMNS) + ", is_closed INTEGER DEFAULT 0"
    conn.execute(f"CREATE TABLE postings ({cols_def})")
    all_cols = POSTING_COLUMNS + ["is_closed"]
    placeholders = ", ".join("?" for _ in all_cols)
    for row in rows:
        vals = [row.get(c) for c in POSTING_COLUMNS] + [row.get("is_closed", 0)]
        conn.execute(f"INSERT INTO postings VALUES ({placeholders})", vals)
    conn.commit()
    conn.close()
    return db


# ---------------------------------------------------------------------------
# load_postings
# ---------------------------------------------------------------------------

def test_load_postings_only_open(tmp_path):
    db = _make_db(tmp_path, [
        {"title": "Data Engineer", "company_name": "Acme", "is_closed": 0},
        {"title": "Closed Role",   "company_name": "Corp", "is_closed": 1},
    ])
    result = load_postings(db)
    assert len(result) == 1
    assert result[0]["title"] == "Data Engineer"


def test_load_postings_has_all_keys(tmp_path):
    db = _make_db(tmp_path, [
        {"title": "ML Engineer", "company_name": "AI Corp", "is_closed": 0},
    ])
    result = load_postings(db)
    for key in POSTING_COLUMNS:
        assert key in result[0], f"chiave mancante: {key}"


# ---------------------------------------------------------------------------
# is_tech_role
# ---------------------------------------------------------------------------

def test_is_tech_role_keeps_tech():
    assert is_tech_role("Data Engineer") is True
    assert is_tech_role("Machine Learning Intern") is True
    assert is_tech_role("DevOps Engineer") is True
    assert is_tech_role("SAP Consultant") is True
    assert is_tech_role("Business Analyst") is True
    assert is_tech_role("Demand Planner Supply Chain") is True


def test_is_tech_role_rejects_non_tech():
    # Solo parole esplicitamente nella blacklist → scartate
    assert is_tech_role("Sales Manager") is False
    assert is_tech_role("Nurse Practitioner") is False
    assert is_tech_role("HR Generalist") is False


def test_is_tech_role_unclassified_kept():
    # Ruoli non in blacklist → tenuti come "unclassified"
    assert is_tech_role("Controller") is True
    assert is_tech_role("Process Analyst") is True


# ---------------------------------------------------------------------------
# prefilter
# ---------------------------------------------------------------------------

def test_prefilter_separates_correctly():
    postings = [
        {"title": "Junior Data Engineer",    "company_name": "A", "requirements_raw": ""},
        {"title": "Senior Software Director","company_name": "B", "requirements_raw": ""},
        {"title": "Sales Manager",           "company_name": "C", "requirements_raw": ""},
    ]
    kept, discarded = prefilter(postings)

    assert len(kept) == 1
    assert kept[0]["title"] == "Junior Data Engineer"
    assert len(discarded) == 2

    reasons = {d["title"]: d["_discard_reason"] for d in discarded}
    assert reasons["Sales Manager"] == "ruolo non tecnico"
    assert reasons["Senior Software Director"] != ""


# ---------------------------------------------------------------------------
# country_ok
# ---------------------------------------------------------------------------

def test_country_ok_in_allowed():
    assert country_ok({"country_code": "DE"}) is True
    assert country_ok({"country_code": "CH"}) is True
    assert country_ok({"country_code": "NL"}) is True


def test_country_ok_not_in_allowed_onsite():
    assert country_ok({"country_code": "IT", "work_mode": "onsite"}) is False
    assert country_ok({"country_code": "US"}) is False


def test_country_ok_empty_country():
    assert country_ok({"country_code": ""}) is True
    assert country_ok({"country_code": None}) is True
    assert country_ok({}) is True


def test_country_ok_remote_single_foreign_country_discarded():
    # remoto ma legato a un solo paese non richiesto → è un lavoro in quel paese
    assert country_ok({"country_code": "FR", "work_mode": "remote"}) is False
    assert country_ok({"country_code": "GB", "work_mode": "remote",
                       "location": "Remote, United Kingdom"}) is False
    assert country_ok({"country_code": "ES", "work_mode": "remote",
                       "location": "Remote, Spain"}) is False
    assert country_ok({"country_code": "IT", "work_mode": "remote"}) is False


def test_country_ok_remote_non_europe():
    # remoto da fuori Europa → scarta
    assert country_ok({"country_code": "US", "work_mode": "remote"}) is False
    assert country_ok({"country_code": "IN", "work_mode": "remote"}) is False


def test_prefilter_discards_wrong_country():
    postings = [
        {"title": "Data Engineer", "country_code": "IT", "work_mode": "onsite", "requirements_raw": ""},
        {"title": "Data Engineer", "country_code": "DE", "requirements_raw": ""},
    ]
    kept, discarded = prefilter(postings)
    assert len(kept) == 1
    assert kept[0]["country_code"] == "DE"
    assert discarded[0]["_discard_reason"] == "paese non in lista (IT)"


# ---------------------------------------------------------------------------
# is_tech_role — consultant qualifier
# ---------------------------------------------------------------------------

def test_is_tech_role_consultant_no_qualifier():
    assert is_tech_role("Sales Consultant") is False      # sales in blacklist
    assert is_tech_role("Marketing Berater") is False     # marketing in blacklist


def test_is_tech_role_consultant_with_it():
    assert is_tech_role("IT Consultant") is True


def test_is_tech_role_consultant_with_tech_qualifier():
    assert is_tech_role("SAP Consultant") is True    # priority 2 via SAP
    assert is_tech_role("Digital Consultant") is True  # priority 1 via digital consultant
    assert is_tech_role("IT Consultant") is True      # priority 1


# ---------------------------------------------------------------------------
# role_category — priorità
# ---------------------------------------------------------------------------

def test_role_category_priority_1():
    for title in [
        "Junior Business Analyst",
        "Scrum Master",
        "Demand Planner",
        "Data Engineer",
    ]:
        result = role_category(title)
        assert result is not None and result[1] == 1, f"atteso priorità 1 per '{title}'"


def test_role_category_priority_2():
    assert role_category("SAP Consultant") == ("consulting_security", 2)
    assert role_category("Cybersecurity Analyst") == ("consulting_security", 2)


def test_role_category_priority_3():
    assert role_category("Software Engineer") == ("software", 3)


def test_role_category_priority_4():
    assert role_category("IT Support Specialist") == ("support_qa", 4)
    assert role_category("QA Engineer") == ("support_qa", 4)


def test_role_category_excludes_hardware_and_non_tech():
    assert role_category("UX Designer") is None
    assert role_category("Ingenieur Elektrotechnik") is None
    assert role_category("ASIC Digital Design Engineer") is None
    assert role_category("Mechanical Engineer") is None
    assert role_category("Sales Consultant") is None


def test_role_category_priority_5():
    assert role_category("Controller") == ("unclassified", 5)
    assert role_category("Process Analyst") == ("unclassified", 5)


def test_role_category_pm_conditional():
    # Con qualifier → priorità 1
    assert role_category("Associate Product Manager") == ("analytics_ai", 1)
    # Senza qualifier → scivola a priorità 5
    result = role_category("Product Manager")
    assert result is not None and result[1] == 5


def test_prefilter_keeps_unclassified():
    postings = [
        {"title": "Controller",    "requirements_raw": ""},
        {"title": "Sales Manager", "requirements_raw": ""},
    ]
    kept, discarded = prefilter(postings)
    assert len(kept) == 1
    assert kept[0]["title"] == "Controller"
    assert kept[0]["_role_category"] == "unclassified"
    assert kept[0]["_role_priority"] == 5
    assert discarded[0]["title"] == "Sales Manager"


def test_prefilter_sorted_by_priority():
    postings = [
        {"title": "Software Engineer", "requirements_raw": ""},  # priority 3
        {"title": "Data Engineer",     "requirements_raw": ""},  # priority 1
        {"title": "Controller",        "requirements_raw": ""},  # priority 5
    ]
    kept, _ = prefilter(postings)
    priorities = [p["_role_priority"] for p in kept]
    assert priorities == sorted(priorities), f"not sorted: {priorities}"


def test_country_ok_remote_de_kept():
    assert country_ok({"country_code": "DE", "work_mode": "remote"}) is True


def test_country_ok_remote_us_discarded():
    assert country_ok({"country_code": "US", "work_mode": "remote"}) is False


# ---------------------------------------------------------------------------
# download_feed
# ---------------------------------------------------------------------------

def test_download_feed_raises_without_gh(tmp_path):
    with patch("app.services.feed_reader.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="gh"):
            download_feed(tmp_path)


# ---------------------------------------------------------------------------
# Blacklist estesa — radici composte tedesche + nuovi termini
# ---------------------------------------------------------------------------

def test_blacklist_discard_verkaufsgebiet():
    # "Verkaufs" è prefisso composto di verkauf → scartato
    assert role_category("Außendienstmitarbeiter für das Verkaufsgebiet") is None


def test_blacklist_discard_facilitair():
    assert role_category("Junior Facilitair Medewerker") is None


def test_blacklist_discard_personalentwicklung_und_recruiting():
    # personal + recruit — entrambe le radici colpiscono
    assert role_category("Praktikum in der Personalentwicklung und Recruiting") is None


def test_blacklist_discard_dangerous_goods():
    assert role_category("Dangerous Goods Specialist") is None


def test_blacklist_discard_medical_fellow():
    assert role_category("Medical Fellow") is None


def test_blacklist_keep_finance_associate():
    # finance non è in blacklist → tenuto
    assert role_category("Finance Associate") is not None


def test_blacklist_keep_data_management():
    # nessun termine in blacklist; "data" non è in blacklist quindi non serve override
    assert role_category("Praktikum Data Management Fertigung") is not None


def test_blacklist_keep_manufacturing_it():
    # manufacturing non è in blacklist; "IT" è override anche se qualcosa matchasse
    assert role_category("Werkstudent im Bereich Manufacturing IT") is not None


def test_blacklist_keep_digital_solutions_engineer():
    assert role_category("Digital Solutions Engineer") is not None


def test_blacklist_personal_data_override():
    # "personal" colpisce la blacklist ma "data" attiva l'override → tenuto
    assert role_category("Personal Data Manager") is not None


def test_blacklist_medical_software_override():
    # "medical" colpisce ma "software" attiva l'override → tenuto
    assert role_category("Medical Device Software Engineer") is not None


# ---------------------------------------------------------------------------
# Priorità 1: serve un ruolo nel titolo, non basta la parola "AI" o "data"
# ---------------------------------------------------------------------------

def test_account_executive_with_ai_domain_is_not_tech():
    # commerciale; "Leonardo.ai" è un nome a dominio, non un ruolo AI
    title = "Account Executive, Leonardo.ai (m/w/d) – Munich (German-speaking)"
    assert role_category(title) is None


def test_hardware_engineer_with_ai_is_not_tech():
    assert role_category("Hardware Systems Engineer - AI Hardware") is None


def test_process_engineer_with_data_science_is_not_tech():
    title = (
        "PreMaster Programm Data Science and Process Control for Semiconductor "
        "Manufacturing - Ingenieur:in für CVD Prozesse (w/m/div)"
    )
    assert role_category(title) is None
    assert role_category("Ingenieur:in für CVD Prozesse") is None


def test_staff_software_engineer_is_software_not_priority_1():
    assert role_category("Staff Software Engineer") == ("software", 3)
    # la parola-tema "AI" non scavalca il ruolo software
    assert role_category("Staff Software Engineer, AI Agents (Python)") == ("software", 3)


@pytest.mark.parametrize("title", [
    "Account Executive, Leonardo.ai (m/w/d) – Munich (German-speaking)",
    "Hardware Systems Engineer - AI Hardware",
    "Ingenieur:in für CVD Prozesse",
    "Staff Software Engineer",
    "Staff Software Engineer, AI Agents (Python)",
])
def test_wrong_titles_never_reach_the_list_as_priority_1(title):
    kept, _ = prefilter([{"title": title, "country_code": "DE", "requirements_raw": ""}])
    assert [p for p in kept if p["_role_priority"] == 1] == []


@pytest.mark.parametrize("title", [
    "Sales Engineer AI",
    "AI Recruiter",
    "Marketing Manager Data & AI",
    "Executive Assistant AI Office",
    "FPGA Engineer Machine Learning",
    "Process Engineer Data Science",
])
def test_topic_words_do_not_rescue_non_target_roles(title):
    assert role_category(title) is None


@pytest.mark.parametrize("title", [
    "Business Analyst",
    "Data Analyst Marketing",          # il ruolo è analyst: resta priorità 1
    "Product Owner",
    "Scrum Master",
    "IT Consultant",
    "BI Developer",
    "Forecasting Specialist",
    "Data Engineer",
    "AI Engineer",
    "Machine Learning Researcher",
    "Research Scientist",
    "Praktikum im Bereich Enterprise Data & AI",   # solo parola-tema, nessun altro ruolo
    "Machine Learning Intern",
    "Werkstudent KI",
])
def test_real_analytics_titles_stay_priority_1(title):
    assert role_category(title) == ("analytics_ai", 1)


def test_software_role_with_commercial_word_stays_software():
    assert role_category("Software Engineer, Sales Tools") == ("software", 3)


# ---------------------------------------------------------------------------
# Seniority
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "Staff Software Engineer",
    "Principal Data Scientist",
    "Head of Data",
    "Head Data Analytics",
    "Lead Data Analyst",
    "Senior Data Analyst",
    "Director AI Research",
    "Staff AI Engineer",
])
def test_senior_titles_are_discarded(title):
    incompatible, reason = seniority_check(title, "")
    assert incompatible is True, title
    assert reason


@pytest.mark.parametrize("title", [
    "Staff Engineer - Internship Program",
    "Lead Data Analyst (Werkstudent Betreuung)",
    "Principal AI Intern",
    "Director Junior Talent AI",
    "Head of Praktikum Program",
])
def test_hard_senior_wins_even_with_junior_or_ai_words(title):
    assert seniority_check(title, "")[0] is True, title


@pytest.mark.parametrize("title", [
    "Junior/Senior Data Analyst",
    "Stage Senior Data Team",
    "Werkstudent Senior Management Reporting",
    "Praktikum Senior Consulting",
    "Internship - Senior Leadership Analytics",
])
def test_junior_word_wins_over_senior(title):
    assert seniority_check(title, "") == (False, "")


@pytest.mark.parametrize("title", [
    "Senior International Data Analyst",   # "International" non è "intern"
    "Senior Backstage Engineer",           # "Backstage" non è "stage"
    "Senior Data Analyst",
])
def test_senior_needs_a_real_junior_word_to_be_kept(title):
    assert seniority_check(title, "")[0] is True, title


def test_prefilter_discards_staff_title_with_ai():
    kept, discarded = prefilter([
        {"title": "Staff Software Engineer, AI Agents (Python)", "country_code": "DE"},
    ])
    assert kept == []
    assert "staff" in discarded[0]["_discard_reason"]


# ---------------------------------------------------------------------------
# Tesi e dottorati
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title", [
    "PhD - Safety Contracts for Physical AI",
    "Ph.D. Position Machine Learning",
    "Promotion - Foundation Models und Agentic AI",
    "Doktorarbeit Data Science",
    "Dissertation im Bereich KI",
    "Master Thesis AI-based Sensorless Edrive Control",
    "Bachelor Thesis Data Analytics",
    "Masterarbeit KI-Agenten",
    "Abschlussarbeit: KI-Agent für Maschinendiagnose",
    "Thesis AI Agent for Automated Machine Diagnostics",
])
def test_posting_kind_thesis(title):
    assert posting_kind(title) == "thesis"


@pytest.mark.parametrize("title", [
    "Junior Data Analyst",
    "Praktikum Data & AI",
    "Mandatory Internship AI Agent",
    "Hypothesis Testing Analyst",     # "thesis" solo come parola intera
    "",
])
def test_posting_kind_job(title):
    assert posting_kind(title) == "job"


def test_prefilter_marks_thesis_but_keeps_it():
    kept, _ = prefilter([
        {"title": "Master Thesis Machine Learning", "country_code": "DE"},
        {"title": "Junior Data Analyst", "country_code": "DE"},
    ])
    assert {p["title"]: p["_kind"] for p in kept} == {
        "Master Thesis Machine Learning": "thesis",
        "Junior Data Analyst": "job",
    }


# ---------------------------------------------------------------------------
# Paesi
# ---------------------------------------------------------------------------

def test_region_allowed_countries():
    assert posting_region({"country_code": "CH"}) == "CH"
    assert posting_region({"country_code": "DE", "work_mode": "remote"}) == "DE"
    assert posting_region({"country_code": "NL", "work_mode": "onsite"}) == "NL"


@pytest.mark.parametrize("country", ["GB", "ES", "FR", "IT", "PL", "US"])
def test_region_other_countries_discarded(country):
    assert posting_region({"country_code": country}) is None
    assert posting_region({"country_code": country, "work_mode": "hybrid",
                           "location": "Europe"}) is None


def test_region_remote_open_to_europe_is_kept():
    assert posting_region({"country_code": "GB", "work_mode": "remote",
                           "location": "Remote, Europe"}) == "remote_eu"
    assert posting_region({"country_code": "FR", "work_mode": "remote",
                           "location": "EMEA"}) == "remote_eu"
    # elenco di sedi che comprende un paese richiesto
    assert posting_region({"country_code": "GB", "work_mode": "remote",
                           "location": "United Kingdom, Germany, The Netherlands"}) == "remote_eu"
    # "Europa" detta nel titolo
    assert posting_region({"country_code": "FR", "work_mode": "remote", "location": "France, Remote",
                           "title": "ML Engineer - EMEA Remote"}) == "remote_eu"


def test_region_remote_outside_europe_discarded_even_if_location_says_europe():
    assert posting_region({"country_code": "US", "work_mode": "remote",
                           "location": "Remote, Europe or US"}) is None


def test_region_unknown_country_is_kept():
    for location in [None, "", "Hybrid", "Remote", "Remote, Global", "In-Office", "N/A"]:
        assert posting_region({"country_code": None, "location": location}) == "unknown", location
    assert posting_region({}) == "unknown"


def test_region_unknown_country_code_but_location_names_foreign_country():
    for location in [
        "United States (Remote)", "Remote US", "Canada (Remote)",
        "Manila, Manila, Philippines", "London, United Kingdom", "Remote, Spain",
    ]:
        assert posting_region({"country_code": None, "location": location}) is None, location


def test_region_unknown_country_with_europe_in_location_is_kept():
    assert posting_region({"country_code": None, "location": "Europe or US"}) == "unknown"
    assert posting_region({"country_code": None, "location": "EMEA"}) == "unknown"
    # il pronome "us" non è il paese
    assert posting_region({"country_code": None, "location": "Work with us remotely"}) == "unknown"


def test_prefilter_sets_region():
    kept, discarded = prefilter([
        {"title": "Data Engineer", "country_code": "DE"},
        {"title": "Data Engineer", "country_code": None},
        {"title": "Data Engineer", "country_code": "GB", "work_mode": "remote", "location": "Europe"},
        {"title": "Data Engineer", "country_code": "GB", "work_mode": "remote", "location": "UK"},
    ])
    assert [p["_region"] for p in kept] == ["DE", "unknown", "remote_eu"]
    assert discarded[0]["_discard_reason"] == "paese non in lista (GB)"
