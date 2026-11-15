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
    prefilter,
    role_category,
)


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


def test_country_ok_remote_europe():
    # remoto da paesi in EUROPE_COUNTRIES → tieni
    assert country_ok({"country_code": "FR", "work_mode": "remote"}) is True
    assert country_ok({"country_code": "GB", "work_mode": "remote"}) is True
    assert country_ok({"country_code": "IT", "work_mode": "remote"}) is True


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
