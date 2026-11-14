import sqlite3
from unittest.mock import patch

import pytest

from app.services.feed_reader import (
    POSTING_COLUMNS,
    download_feed,
    is_tech_role,
    load_postings,
    prefilter,
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
    assert is_tech_role("Sales Manager") is False
    assert is_tech_role("Baker") is False
    assert is_tech_role("HR Generalist") is False
    assert is_tech_role("Responsabile Commerciale") is False


# ---------------------------------------------------------------------------
# prefilter
# ---------------------------------------------------------------------------

def test_prefilter_separates_correctly():
    postings = [
        {"title": "Junior Data Engineer",    "company_name": "A", "requirements_raw": ""},
        {"title": "Senior Software Director","company_name": "B", "requirements_raw": ""},
        {"title": "Chef de Cuisine",         "company_name": "C", "requirements_raw": ""},
    ]
    kept, discarded = prefilter(postings)

    assert len(kept) == 1
    assert kept[0]["title"] == "Junior Data Engineer"
    assert len(discarded) == 2

    reasons = {d["title"]: d["_discard_reason"] for d in discarded}
    assert reasons["Chef de Cuisine"] == "ruolo non tecnico"
    assert reasons["Senior Software Director"] != ""


# ---------------------------------------------------------------------------
# download_feed
# ---------------------------------------------------------------------------

def test_download_feed_raises_without_gh(tmp_path):
    with patch("app.services.feed_reader.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="gh"):
            download_feed(tmp_path)
