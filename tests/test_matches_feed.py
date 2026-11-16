"""Test di GET /api/matches/feed: database sqlite di prova, feed finto,
nessuna chiamata di rete."""
import importlib
import subprocess
from unittest.mock import patch

import pytest

FEED_ROWS = [
    {"title": "Junior Data Scientist", "company_name": "Acme", "country_code": "DE",
     "requirements_raw": "Rust, Scala, Kafka", "source_url": "https://example.test/ds",
     "first_seen_at": "2026-11-01T10:00:00"},
    {"title": "Junior Data Analyst", "company_name": "Acme", "country_code": "NL",
     "requirements_raw": "Python, SQL", "source_url": "https://example.test/da",
     "first_seen_at": "2026-11-02T10:00:00"},
    {"title": "Sales Representative", "company_name": "Acme", "country_code": "DE",
     "requirements_raw": "Python, SQL"},
]


@pytest.fixture
def api(orm, db):
    """App minima con il solo router dei match e il database di prova."""
    fastapi = importlib.import_module("fastapi")
    testclient = importlib.import_module("fastapi.testclient")
    matches = importlib.import_module("app.routers.matches")
    config = importlib.import_module("app.core.config")

    app = fastapi.FastAPI()
    app.include_router(matches.router)

    def _get_db():
        yield db

    app.dependency_overrides[orm.database.get_db] = _get_db
    client = testclient.TestClient(app)
    client.headers["X-API-Token"] = config.API_TOKEN
    client.matches = matches
    client.api_token = config.API_TOKEN
    return client


def test_feed_returns_matches_for_user(orm, api, add_user, make_feed):
    uid = add_user("a@example.test", ["Python", "SQL"])
    feed = make_feed(FEED_ROWS)
    with patch.object(orm.pipeline, "download_feed", return_value=feed) as dl:
        res = api.get("/api/matches/feed", params={"user_id": uid})

    assert res.status_code == 200
    dl.assert_called_once_with(api.matches.FEED_CACHE_DIR)
    assert res.json() == [
        {
            "title": "Junior Data Analyst",
            "company_name": "Acme",
            "country_code": "NL",
            "region": "NL",
            "kind": "job",
            "source_url": "https://example.test/da",
            "priority": 1,
            "category": "analytics_ai",
            "coverage": 1.0,
            "below_threshold": False,
            "matched_skills": ["python", "sql"],
            "missing_required": [],
            "missing_nice": [],
            "skills_measured": 2,
            "first_seen_at": "2026-11-02T10:00:00",
            "description": "Python, SQL",
            "is_new": False,
        },
        {
            "title": "Junior Data Scientist",
            "company_name": "Acme",
            "country_code": "DE",
            "region": "DE",
            "kind": "job",
            "source_url": "https://example.test/ds",
            "priority": 1,
            "category": "analytics_ai",
            "coverage": 0.0,
            "below_threshold": True,
            "matched_skills": [],
            "missing_required": ["kafka", "rust", "scala"],
            "missing_nice": [],
            "skills_measured": 3,
            "first_seen_at": "2026-11-01T10:00:00",
            "description": "Rust, Scala, Kafka",
            "is_new": False,
        },
    ]


def test_feed_uses_skills_of_requested_user(orm, api, add_user, make_feed):
    add_user("a@example.test", ["Python", "SQL"])
    uid_b = add_user("b@example.test", ["Rust", "Scala", "Kafka"])
    feed = make_feed(FEED_ROWS)
    with patch.object(orm.pipeline, "download_feed", return_value=feed):
        res = api.get("/api/matches/feed", params={"user_id": uid_b})

    assert [(m["title"], m["coverage"]) for m in res.json()] == [
        ("Junior Data Scientist", 1.0),
        ("Junior Data Analyst", 0.0),
    ]


def test_feed_requires_token(orm, api, add_user):
    if not api.api_token:
        pytest.skip("API_TOKEN non configurato: l'API non è protetta")
    uid = add_user("a@example.test", ["Python"])
    with patch.object(orm.pipeline, "download_feed", side_effect=AssertionError("non deve arrivarci")):
        res = api.get("/api/matches/feed", params={"user_id": uid},
                      headers={"X-API-Token": "sbagliato"})
    assert res.status_code == 401


def test_feed_unknown_user_is_404_without_download(orm, api):
    with patch.object(orm.pipeline, "download_feed", side_effect=AssertionError("non deve scaricare")):
        res = api.get("/api/matches/feed", params={"user_id": "non-esiste"})
    assert res.status_code == 404
    assert res.json()["detail"] == "Utente non trovato"


def test_feed_route_is_not_shadowed_by_match_id(api):
    # Senza user_id deve rispondere la route /feed (422), non /{match_id}
    # con "feed" come id (sarebbe 404 "Match non trovato").
    res = api.get("/api/matches/feed")
    assert res.status_code == 422


def test_fresh_cache_is_not_downloaded_again(api, add_user, make_feed, tmp_path):
    """Con jobs.sqlite recente in cache l'endpoint non lancia `gh`."""
    uid = add_user("a@example.test", ["Python", "SQL"])
    make_feed(FEED_ROWS, name="cache/jobs.sqlite")
    with patch.object(api.matches, "FEED_CACHE_DIR", tmp_path / "cache"), \
         patch("subprocess.run", side_effect=AssertionError("non deve riscaricare")), \
         patch("shutil.which", return_value=None):
        res = api.get("/api/matches/feed", params={"user_id": uid})
    assert res.status_code == 200
    assert len(res.json()) == 2


@pytest.mark.parametrize("error", [
    RuntimeError("Il comando 'gh' (GitHub CLI) non è disponibile sul sistema."),
    subprocess.CalledProcessError(1, ["gh", "release", "download"]),
    OSError("file corrotto"),
])
def test_feed_unavailable_is_503_in_italian(orm, api, add_user, error):
    uid = add_user("a@example.test", ["Python"])
    with patch.object(orm.pipeline, "download_feed", side_effect=error):
        res = api.get("/api/matches/feed", params={"user_id": uid})
    assert res.status_code == 503
    assert res.json()["detail"] == api.matches.FEED_UNAVAILABLE
    assert "feed degli annunci non è disponibile" in res.json()["detail"]


def test_gh_missing_and_no_cache_is_503(api, add_user, tmp_path):
    """Percorso reale di download_feed: cache vuota e `gh` assente."""
    uid = add_user("a@example.test", ["Python"])
    with patch.object(api.matches, "FEED_CACHE_DIR", tmp_path / "vuota"), \
         patch("shutil.which", return_value=None), \
         patch("subprocess.run", side_effect=AssertionError("nessuna rete nei test")):
        res = api.get("/api/matches/feed", params={"user_id": uid})
    assert res.status_code == 503
    assert res.json()["detail"] == api.matches.FEED_UNAVAILABLE


def test_feed_marks_thesis_and_unknown_country(orm, api, add_user, make_feed):
    uid = add_user("a@example.test", ["Python", "SQL"])
    feed = make_feed(FEED_ROWS + [
        {"title": "Master Thesis Machine Learning", "company_name": "Acme", "country_code": "DE",
         "requirements_raw": "Python, SQL"},
        {"title": "Junior Business Analyst", "company_name": "Acme", "country_code": None,
         "location": "Hybrid", "requirements_raw": "Python, SQL"},
        {"title": "Junior BI Analyst", "company_name": "Acme", "country_code": "GB",
         "work_mode": "remote", "location": "Remote, United Kingdom", "requirements_raw": "Python, SQL"},
    ])
    with patch.object(orm.pipeline, "download_feed", return_value=feed):
        res = api.get("/api/matches/feed", params={"user_id": uid})

    assert res.status_code == 200
    by_title = {m["title"]: m for m in res.json()}
    assert by_title["Master Thesis Machine Learning"]["kind"] == "thesis"
    assert by_title["Junior Data Analyst"]["kind"] == "job"
    assert by_title["Junior Business Analyst"]["region"] == "unknown"
    assert by_title["Junior Business Analyst"]["country_code"] is None
    assert "Junior BI Analyst" not in by_title


# ---------------------------------------------------------------------------
# PATCH /api/matches/{id}/status: stati della candidatura
# ---------------------------------------------------------------------------

def _add_match(orm, db, user_id: str) -> str:
    m = orm.models
    session = m.SearchSession(user_id=user_id, role_title="Data Analyst")
    db.add(session)
    db.flush()
    listing = m.JobListing(session_id=session.id, title="Junior Data Analyst", company_name="Acme")
    db.add(listing)
    db.flush()
    match = m.Match(session_id=session.id, listing_id=listing.id)
    db.add(match)
    db.commit()
    return match.id


@pytest.mark.parametrize("status", ["waiting", "accepted", "applied", "interview", "rejected"])
def test_status_accepts_application_states(orm, db, api, add_user, status):
    uid = add_user("a@example.test", ["Python"])
    mid = _add_match(orm, db, uid)
    res = api.patch(f"/api/matches/{mid}/status", json={"status": status})
    assert res.status_code == 200
    assert res.json()["status"] == status


def test_status_rejects_unknown_value(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    mid = _add_match(orm, db, uid)
    res = api.patch(f"/api/matches/{mid}/status", json={"status": "boh"})
    assert res.status_code == 400
