"""Candidature: salvataggio dal feed, stati, raggruppamenti, ordinamento,
"Nuovi da ieri" e migrazione additiva.

Nessuna rete, nessun LLM e nessun database reale: ogni prova usa un sqlite
temporaneo (fixture `db`) e il guard di conftest.py punta DATABASE_URL altrove.
"""
import hashlib
import importlib
import json
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import pytest

TODAY = date(2026, 11, 15)


@pytest.fixture
def tracking(orm):
    return importlib.import_module("app.services.tracking")


# ---------------------------------------------------------------------------
# Funzioni pure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seen, expected", [
    ("2026-11-15T10:00:00", True),    # oggi
    ("2026-11-14T00:00:00", True),    # ieri alle 00:00: il confine è incluso
    ("2026-11-14T23:59:59", True),
    ("2026-11-13T23:59:59", False),   # prima di ieri
    ("2026-11-16T09:00:00", False),   # nel futuro: dato sospetto
    (None, False),
    ("", False),
    ("non una data", False),
])
def test_is_new_since_boundaries(tracking, seen, expected):
    assert tracking.is_new_since(seen, TODAY) is expected


def test_is_new_since_accepts_timezone_suffix(tracking):
    assert tracking.is_new_since("2026-11-15T10:00:00Z", TODAY) is True


@pytest.mark.parametrize("coverage, priority, expected", [
    (0.6, 2, True),      # esattamente alla soglia
    (1.0, 5, True),
    (0.59, 1, False),    # sotto la soglia: anche con priorità 1 non è un "nuovo"
    (0.0, 1, False),
    (None, 1, True),     # non misurabile ma di priorità 1
    (None, 2, False),    # non misurabile e priorità bassa
])
def test_qualifies_as_new_rule(tracking, coverage, priority, expected):
    assert tracking.qualifies_as_new("2026-11-15T08:00:00", coverage, priority, TODAY) is expected


def test_old_posting_never_qualifies_as_new(tracking):
    assert tracking.qualifies_as_new("2026-11-01T08:00:00", 1.0, 1, TODAY) is False


def test_feed_marks_is_new_in_pipeline(orm):
    """match_postings: `is_new` segue la regola, con la data di riferimento passata."""
    pipeline = orm.pipeline
    base = {"company_name": "Acme", "country_code": "DE", "source_url": "u"}
    postings = [
        {**base, "title": "Junior Data Analyst", "requirements_raw": "Python, SQL",
         "first_seen_at": "2026-11-15T07:00:00"},                         # nuovo, 100%
        {**base, "title": "Junior Data Scientist", "requirements_raw": "Rust, Scala, Kafka",
         "first_seen_at": "2026-11-15T07:00:00"},                         # nuovo ma 0%
        {**base, "title": "Junior BI Analyst", "requirements_raw": "Python, SQL",
         "first_seen_at": "2026-11-01T07:00:00"},                         # vecchio
        {**base, "title": "Junior Data Engineer", "requirements_raw": "Nessuna skill nota qui",
         "first_seen_at": "2026-11-14T07:00:00"},                         # nuovo, non misurabile, priorità 1
    ]
    out = {r["title"]: r for r in pipeline.match_postings(postings, ["Python", "SQL"], today=TODAY)}
    assert out["Junior Data Analyst"]["is_new"] is True
    assert out["Junior Data Scientist"]["is_new"] is False
    assert out["Junior BI Analyst"]["is_new"] is False
    assert out["Junior Data Engineer"]["coverage"] is None
    assert out["Junior Data Engineer"]["is_new"] is True


def test_feed_carries_the_text_coverage_is_computed_on(orm):
    postings = [{
        "title": "Junior Data Analyst", "company_name": "Acme", "country_code": "DE",
        "requirements_raw": "Python, SQL", "description": "Testo lungo e diverso",
        "source_url": "u", "first_seen_at": "2026-11-01T00:00:00",
    }]
    out = orm.pipeline.match_postings(postings, ["Python"], today=TODAY)
    assert out[0]["description"] == "Python, SQL"


@pytest.mark.parametrize("title, coverage, expected", [
    ("Junior Data Analyst", 0.8, False),
    ("Junior Data Analyst", None, False),   # non misurabile non basta per dirlo fuori profilo
    ("Junior Data Analyst", 0.0, True),    # misurata e a zero
    ("Pflegefachfrau 80-100%", 0.5, True), # titolo non tech
    ("Hotelfachfrau", None, True),         # ruolo non classificabile e nessun segnale dalle skill
    ("Junior Platform Specialist", 1.0, False),   # non classificabile, ma le skill coincidono
    ("Junior Platform Specialist", None, True),
    ("Junior Platform Specialist", 0.0, True),
    ("", 0.9, True),
])
def test_is_off_profile(tracking, title, coverage, expected):
    assert tracking.is_off_profile(title, coverage) is expected


@pytest.mark.parametrize("scores, expected", [
    ([0.6, 0.6, 0.6], True),
    ([0.6, 0.6000001], True),      # differenza trascurabile
    ([0.6, 0.7], False),
    ([0.6], False),                # un solo annuncio: nulla da confrontare
    ([], False),
    ([None, 0.0], True),
])
def test_scores_are_uniform(tracking, scores, expected):
    assert tracking.scores_are_uniform(scores) is expected


def test_match_sort_key_puts_off_profile_last_and_unmeasured_after(tracking):
    items = [
        {"id": "off_high", "coverage": 0.9, "off_profile": True},
        {"id": "none", "coverage": None, "off_profile": False},
        {"id": "low", "coverage": 0.2, "off_profile": False},
        {"id": "high", "coverage": 0.8, "off_profile": False},
        {"id": "off_none", "coverage": None, "off_profile": True},
    ]
    ordered = [i["id"] for i in sorted(items, key=tracking.match_sort_key)]
    assert ordered == ["high", "low", "none", "off_high", "off_none"]


def test_group_by_status_fixed_order_all_groups_present(tracking):
    groups = tracking.group_by_status([])
    assert [g["status"] for g in groups] == [
        "saved", "applied", "waiting", "interview", "rejected", "accepted",
    ]
    assert [g["label"] for g in groups] == [
        "Salvate", "Inviate", "In attesa", "Colloquio", "Rifiutate", "Accettate",
    ]
    assert all(g["count"] == 0 and g["items"] == [] for g in groups)


def test_group_by_status_ignores_untracked_and_sorts_recent_first(tracking):
    rows = [
        {"id": 1, "status": "applied", "created_at": datetime(2026, 11, 1)},
        {"id": 2, "status": "applied", "created_at": datetime(2026, 11, 9)},
        {"id": 3, "status": "new", "created_at": datetime(2026, 11, 10)},
        {"id": 4, "status": "discarded", "created_at": datetime(2026, 11, 10)},
        {"id": 5, "status": "accepted", "created_at": datetime(2026, 11, 2)},
    ]
    by_status = {g["status"]: g for g in tracking.group_by_status(rows)}
    assert [r["id"] for r in by_status["applied"]["items"]] == [2, 1]
    assert by_status["applied"]["count"] == 2
    assert [r["id"] for r in by_status["accepted"]["items"]] == [5]
    assert sum(g["count"] for g in by_status.values()) == 3  # new e discarded non ci sono


# ---------------------------------------------------------------------------
# API: salvataggio dal feed, candidature, ricerche
# ---------------------------------------------------------------------------

AD = {
    "title": "Junior Data Analyst",
    "company_name": "Acme",
    "source_url": "https://example.test/da",
    "country_code": "NL",
    "region": "NL",
    "description": "Python, SQL, Kafka",
    "first_seen_at": "2026-11-14T10:00:00",
}


@pytest.fixture
def api(orm, db):
    fastapi = importlib.import_module("fastapi")
    testclient = importlib.import_module("fastapi.testclient")
    matches = importlib.import_module("app.routers.matches")
    sessions = importlib.import_module("app.routers.sessions")
    config = importlib.import_module("app.core.config")

    app = fastapi.FastAPI()
    app.include_router(matches.router)
    app.include_router(sessions.router)

    def _get_db():
        yield db

    app.dependency_overrides[orm.database.get_db] = _get_db
    client = testclient.TestClient(app)
    client.headers["X-API-Token"] = config.API_TOKEN
    return client


def _save(api, uid, **over):
    return api.post("/api/matches/from-feed", json={"user_id": uid, **AD, **over})


def test_save_creates_match_listing_posting_and_reserved_session(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python", "SQL"])
    res = _save(api, uid)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["status"] == "saved"
    assert body["origin"] == "feed"
    assert body["country_code"] == "NL"
    # la copertura è ricalcolata dal server: python e sql sì, kafka no -> 2 su 3 skill
    assert body["skills_measured"] == 3
    assert body["have"] == ["python", "sql"]
    assert body["missing_required"] == ["kafka"]
    assert body["coverage"] == pytest.approx(0.667, abs=0.001)
    assert body["listing"]["title"] == "Junior Data Analyst"
    assert body["listing"]["source_url"] == "https://example.test/da"
    assert body["listing"]["requirements_raw"] == "Python, SQL, Kafka"

    m = orm.models
    sessions = db.query(m.SearchSession).filter_by(user_id=uid).all()
    assert [(s.search_mode, s.role_title, s.status) for s in sessions] == [("feed", "Dal feed", "completed")]
    assert db.query(m.JobPosting).one().country_code == "NL"
    assert json.loads(db.query(m.Match).one().matched_skills) == ["python", "sql"]


def test_client_cannot_inject_a_coverage(orm, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    res = _save(api, uid, coverage=1.0, skills_measured=99)
    assert res.status_code == 200
    assert res.json()["coverage"] == pytest.approx(0.333, abs=0.001)


def test_save_is_idempotent_and_does_not_downgrade(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python", "SQL"])
    first = _save(api, uid).json()
    api.patch(f"/api/matches/{first['id']}/status", json={"status": "applied"})

    again = _save(api, uid)  # stesso annuncio, "Salva" di nuovo
    assert again.json()["id"] == first["id"]
    assert again.json()["status"] == "applied"  # non torna "saved"

    m = orm.models
    assert db.query(m.Match).count() == 1
    assert db.query(m.JobListing).count() == 1
    assert db.query(m.SearchSession).filter_by(user_id=uid, search_mode="feed").count() == 1


def test_save_with_explicit_status_sets_it(orm, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    res = _save(api, uid, status="interview")
    assert res.json()["status"] == "interview"
    # e uno stato esplicito può cambiare una candidatura già salvata
    assert _save(api, uid, status="waiting").json()["status"] == "waiting"


@pytest.mark.parametrize("bad", ["new", "discarded", "boh"])
def test_save_rejects_non_candidature_status(orm, db, api, add_user, bad):
    uid = add_user("a@example.test", ["Python"])
    res = _save(api, uid, status=bad)
    assert res.status_code == 400
    assert orm.models.Match.__name__ and db.query(orm.models.Match).count() == 0


def test_save_unknown_user_is_404(api):
    assert _save(api, "non-esiste").status_code == 404


def test_save_reuses_a_match_from_an_older_search(orm, db, api, add_user):
    """Lo stesso annuncio trovato da una ricerca vecchia non diventa un doppione."""
    uid = add_user("a@example.test", ["Python"])
    m = orm.models
    s = m.SearchSession(user_id=uid, role_title="Data Analyst")
    db.add(s); db.flush()
    l = m.JobListing(session_id=s.id, title="Junior Data Analyst", company_name="Acme",
                     source_url=AD["source_url"], requirements_raw="Python, SQL, Kafka")
    db.add(l); db.flush()
    old = m.Match(session_id=s.id, listing_id=l.id, score=0.6, status="new")
    db.add(old); db.commit()

    res = _save(api, uid)
    assert res.json()["id"] == old.id
    assert res.json()["status"] == "saved"          # un "new" diventa candidatura
    assert res.json()["origin"] == "search"
    assert db.query(m.Match).count() == 1
    assert db.query(m.SearchSession).filter_by(search_mode="feed").count() == 0  # niente ricerca riservata inutile


def test_save_without_url_dedups_by_content(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    a = _save(api, uid, source_url=None).json()
    b = _save(api, uid, source_url=None).json()
    assert a["id"] == b["id"]
    assert db.query(orm.models.Match).count() == 1


def test_reserved_session_is_hidden_from_searches_but_keeps_ownership(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    m = orm.models
    real = m.SearchSession(user_id=uid, role_title="Data Analyst", search_mode="market")
    db.add(real); db.commit()
    _save(api, uid)

    listed = api.get(f"/api/users/{uid}/sessions").json()
    overview = api.get(f"/api/users/{uid}/sessions/overview").json()
    assert [s["role_title"] for s in listed] == ["Data Analyst"]
    assert [s["role_title"] for s in overview] == ["Data Analyst"]
    assert db.query(m.SearchSession).filter_by(user_id=uid).count() == 2


def test_reserved_session_cannot_be_run(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    _save(api, uid)
    feed_session = db.query(orm.models.SearchSession).filter_by(search_mode="feed").one()
    res = api.post(f"/api/users/{uid}/sessions/{feed_session.id}/run")
    assert res.status_code == 400
    assert feed_session.status == "completed"


def test_users_do_not_share_the_reserved_session(orm, db, api, add_user):
    a = add_user("a@example.test", ["Python"])
    b = add_user("b@example.test", ["Python"])
    _save(api, a)
    _save(api, b)
    assert db.query(orm.models.SearchSession).filter_by(search_mode="feed").count() == 2
    assert db.query(orm.models.Match).count() == 2


# --- /tracked ---------------------------------------------------------------

def test_tracked_groups_all_six_states_in_order(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    res = api.get("/api/matches/tracked", params={"user_id": uid})
    assert res.status_code == 200
    assert [(g["status"], g["label"], g["count"]) for g in res.json()] == [
        ("saved", "Salvate", 0), ("applied", "Inviate", 0), ("waiting", "In attesa", 0),
        ("interview", "Colloquio", 0), ("rejected", "Rifiutate", 0), ("accepted", "Accettate", 0),
    ]


def test_tracked_lists_only_candidature_states_with_country_and_documents(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python", "SQL"])
    m = orm.models

    saved = _save(api, uid).json()
    waiting = _save(api, uid, title="Junior BI Analyst", source_url="https://example.test/bi",
                    status="waiting", country_code="DE", region="DE").json()
    # un risultato di ricerca ancora "new" e uno scartato NON sono candidature
    s = m.SearchSession(user_id=uid, role_title="Data Analyst", search_mode="market")
    db.add(s); db.flush()
    for status in ("new", "discarded"):
        l = m.JobListing(session_id=s.id, title=f"X {status}", company_name="Acme")
        db.add(l); db.flush()
        db.add(m.Match(session_id=s.id, listing_id=l.id, status=status))
    db.add(m.GeneratedDocument(match_id=saved["id"], doc_type="cv", content="CV"))
    db.add(m.GeneratedDocument(match_id=saved["id"], doc_type="cover_letter", content="Lettera"))
    db.commit()

    groups = {g["status"]: g for g in api.get("/api/matches/tracked", params={"user_id": uid}).json()}
    assert groups["saved"]["count"] == 1 and groups["waiting"]["count"] == 1
    assert sum(g["count"] for g in groups.values()) == 2

    row = groups["saved"]["items"][0]
    assert row["id"] == saved["id"]
    assert row["country_code"] == "NL"
    assert row["listing"]["company_name"] == "Acme"
    assert sorted(d["doc_type"] for d in row["documents"]) == ["cover_letter", "cv"]
    assert all("content" not in d for d in row["documents"])  # il testo si apre dal dettaglio
    assert groups["waiting"]["items"][0]["id"] == waiting["id"]
    assert groups["waiting"]["items"][0]["country_code"] == "DE"


def test_tracked_only_shows_own_candidature(orm, api, add_user):
    a = add_user("a@example.test", ["Python"])
    b = add_user("b@example.test", ["Python"])
    _save(api, a)
    counts = {g["status"]: g["count"] for g in api.get("/api/matches/tracked", params={"user_id": b}).json()}
    assert sum(counts.values()) == 0


def test_tracked_unknown_user_is_404_and_route_is_not_shadowed(api):
    assert api.get("/api/matches/tracked", params={"user_id": "non-esiste"}).status_code == 404
    assert api.get("/api/matches/tracked").status_code == 422  # non letto come {match_id}


def test_status_menu_removal_returns_match_to_untracked(orm, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    mid = _save(api, uid, status="applied").json()["id"]
    assert api.patch(f"/api/matches/{mid}/status", json={"status": "new"}).status_code == 200
    counts = {g["status"]: g["count"] for g in api.get("/api/matches/tracked", params={"user_id": uid}).json()}
    assert sum(counts.values()) == 0
    # e ri-salvarlo lo riporta tra le candidature, sullo stesso match
    assert _save(api, uid).json()["id"] == mid
    assert _save(api, uid).json()["status"] == "saved"


def test_get_match_has_the_same_coverage_metric(orm, api, add_user):
    uid = add_user("a@example.test", ["Python", "SQL"])
    saved = _save(api, uid).json()
    detail = api.get(f"/api/matches/{saved['id']}").json()
    assert (detail["coverage"], detail["skills_measured"], detail["have"]) == (
        saved["coverage"], saved["skills_measured"], saved["have"],
    )


# --- Ricerche fatte: metrica unica, pertinenza, raggruppamento ---------------

def _search_with(orm, db, uid, rows):
    """Una ricerca con match già nel database. rows: (titolo, testo, score)."""
    m = orm.models
    s = m.SearchSession(user_id=uid, role_title="Data Analyst", search_mode="market", status="completed")
    db.add(s); db.flush()
    ids = {}
    for title, text, score in rows:
        l = m.JobListing(session_id=s.id, title=title, company_name="Acme", requirements_raw=text)
        db.add(l); db.flush()
        mt = m.Match(session_id=s.id, listing_id=l.id, score=score, status="new")
        db.add(mt); db.flush()
        ids[title] = mt.id
    db.commit()
    return s.id, ids


def test_search_matches_use_feed_coverage_and_group_off_profile_last(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python", "SQL"])
    sid, _ = _search_with(orm, db, uid, [
        ("Pflegefachfrau 80-100%", "Python, SQL", 0.6),           # titolo non tech
        ("Junior Data Scientist", "Rust, Scala, Kafka", 0.6),     # copertura 0
        ("Junior BI Analyst", "Python, SQL, Kafka", 0.6),         # 2 di 3
        ("Junior Data Analyst", "Python, SQL", 0.6),              # 2 di 2
        ("Junior Data Engineer", "Nessuna skill nota", 0.6),      # non misurabile
    ])
    rows = api.get(f"/api/users/{uid}/sessions/{sid}/matches").json()

    assert [r["listing"]["title"] for r in rows] == [
        "Junior Data Analyst",        # 100%
        "Junior BI Analyst",          # 67%
        "Junior Data Engineer",       # non misurabile, ma legato al profilo
        "Pflegefachfrau 80-100%",     # da qui «Poco legati al tuo profilo»
        "Junior Data Scientist",
    ]
    by_title = {r["listing"]["title"]: r for r in rows}
    assert by_title["Junior Data Analyst"]["coverage"] == 1.0
    assert by_title["Junior Data Analyst"]["skills_measured"] == 2
    assert by_title["Junior BI Analyst"]["have"] == ["python", "sql"]
    assert by_title["Junior BI Analyst"]["missing_required"] == ["kafka"]
    assert [r["off_profile"] for r in rows] == [False, False, False, True, True]
    assert all(r["origin"] == "search" for r in rows)


def test_uniform_pertinenza_is_flagged(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    sid, _ = _search_with(orm, db, uid, [
        ("Junior Data Analyst", "Python", 0.6),
        ("Junior BI Analyst", "Python", 0.6),
    ])
    rows = api.get(f"/api/users/{uid}/sessions/{sid}/matches").json()
    assert all(r["pertinenza_uniform"] is True for r in rows)
    assert all(r["score"] == 0.6 for r in rows)  # il numero resta, non viene toccato


def test_varied_pertinenza_is_not_flagged(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    sid, _ = _search_with(orm, db, uid, [
        ("Junior Data Analyst", "Python", 0.9),
        ("Junior BI Analyst", "Python", 0.5),
    ])
    rows = api.get(f"/api/users/{uid}/sessions/{sid}/matches").json()
    assert all(r["pertinenza_uniform"] is False for r in rows)


def test_status_filter_still_works_on_session_matches(orm, db, api, add_user):
    uid = add_user("a@example.test", ["Python"])
    sid, ids = _search_with(orm, db, uid, [
        ("Junior Data Analyst", "Python", 0.6), ("Junior BI Analyst", "Python", 0.6),
    ])
    api.patch(f"/api/matches/{ids['Junior BI Analyst']}/status", json={"status": "applied"})
    rows = api.get(f"/api/users/{uid}/sessions/{sid}/matches", params={"status": "applied"}).json()
    assert [r["listing"]["title"] for r in rows] == ["Junior BI Analyst"]


# --- documenti ---------------------------------------------------------------

def test_save_documents_replaces_by_type_and_marks_saved(orm, db, add_user, tracking):
    uid = add_user("a@example.test", ["Python"])
    m = orm.models
    s = m.SearchSession(user_id=uid, role_title="x"); db.add(s); db.flush()
    l = m.JobListing(session_id=s.id, title="t", company_name="c"); db.add(l); db.flush()
    mt = m.Match(session_id=s.id, listing_id=l.id, status="new"); db.add(mt); db.commit()

    tracking.save_documents(db, mt, {"cv": "CV uno", "cover_letter": "Lettera uno"}, "modello-a")
    assert mt.status == "saved"
    tracking.save_documents(db, mt, {"cv": "CV due", "boh": "ignorato", "email": ""}, "modello-b")

    docs = {d.doc_type: d for d in db.query(m.GeneratedDocument).filter_by(match_id=mt.id)}
    assert set(docs) == {"cv", "cover_letter"}               # un documento per tipo
    assert docs["cv"].content == "CV due" and docs["cv"].llm_model == "modello-b"
    assert docs["cover_letter"].content == "Lettera uno"


def test_save_documents_keeps_a_later_status(orm, db, add_user, tracking):
    uid = add_user("a@example.test", ["Python"])
    m = orm.models
    s = m.SearchSession(user_id=uid, role_title="x"); db.add(s); db.flush()
    l = m.JobListing(session_id=s.id, title="t", company_name="c"); db.add(l); db.flush()
    mt = m.Match(session_id=s.id, listing_id=l.id, status="interview"); db.add(mt); db.commit()
    tracking.save_documents(db, mt, {"cv": "CV"}, None)
    assert mt.status == "interview"


@pytest.fixture
def apply_api(orm, db):
    fastapi = importlib.import_module("fastapi")
    testclient = importlib.import_module("fastapi.testclient")
    applications = importlib.import_module("app.routers.applications")
    matches = importlib.import_module("app.routers.matches")
    config = importlib.import_module("app.core.config")

    app = fastapi.FastAPI()
    app.include_router(applications.router)
    app.include_router(matches.router)

    def _get_db():
        yield db

    app.dependency_overrides[orm.database.get_db] = _get_db
    client = testclient.TestClient(app)
    client.headers["X-API-Token"] = config.API_TOKEN
    client.applications = applications
    return client


def _fake_generation(applications):
    listing = {"title": "Junior Data Analyst", "company_name": "Acme", "location": None,
               "requirements_raw": "Python", "source_url": AD["source_url"]}
    return (
        patch.object(applications.ApplicationBuilder, "fetch_listing", AsyncMock(return_value=listing)),
        patch.object(applications.DocumentGenerator, "generate",
                     AsyncMock(side_effect=lambda t, *a, **k: f"testo {t}")),
    )


def test_generate_with_match_id_saves_documents_on_the_candidatura(orm, db, apply_api, add_user):
    uid = add_user("a@example.test", ["Python"])
    mid = apply_api.post("/api/matches/from-feed", json={"user_id": uid, **AD}).json()["id"]

    fetch, gen = _fake_generation(apply_api.applications)
    with fetch, gen:
        res = apply_api.post("/api/applications/generate",
                             data={"user_id": uid, "url": AD["source_url"], "match_id": mid})
    assert res.status_code == 200, res.text
    assert res.json()["match_id"] == mid
    assert res.json()["documents"] == {"cv": "testo cv", "cover_letter": "testo cover_letter"}

    docs = {d.doc_type: d.content for d in db.query(orm.models.GeneratedDocument).filter_by(match_id=mid)}
    assert docs == {"cv": "testo cv", "cover_letter": "testo cover_letter"}

    rows = {g["status"]: g for g in apply_api.get("/api/matches/tracked", params={"user_id": uid}).json()}
    assert sorted(d["doc_type"] for d in rows["saved"]["items"][0]["documents"]) == ["cover_letter", "cv"]


def test_generate_without_match_id_saves_nothing(orm, db, apply_api, add_user):
    uid = add_user("a@example.test", ["Python"])
    fetch, gen = _fake_generation(apply_api.applications)
    with fetch, gen:
        res = apply_api.post("/api/applications/generate", data={"user_id": uid, "url": AD["source_url"]})
    assert res.status_code == 200
    assert res.json()["match_id"] is None
    assert db.query(orm.models.GeneratedDocument).count() == 0
    assert db.query(orm.models.Match).count() == 0


def test_generate_rejects_someone_elses_match_before_calling_the_llm(orm, db, apply_api, add_user):
    a = add_user("a@example.test", ["Python"])
    b = add_user("b@example.test", ["Python"])
    mid = apply_api.post("/api/matches/from-feed", json={"user_id": a, **AD}).json()["id"]

    fetch, gen = _fake_generation(apply_api.applications)
    with fetch as f, gen as g:
        res = apply_api.post("/api/applications/generate",
                             data={"user_id": b, "url": AD["source_url"], "match_id": mid})
    assert res.status_code == 404
    f.assert_not_called()
    g.assert_not_called()
    assert db.query(orm.models.GeneratedDocument).count() == 0


# ---------------------------------------------------------------------------
# Migrazione: solo additiva, nessun dato esistente toccato
# ---------------------------------------------------------------------------

# Le colonne delle tabelle che le candidature usano. Se qualcuno ne aggiunge o
# ne toglie una, questo test lo dice: la scelta presa è "nessuna colonna nuova".
EXPECTED_COLUMNS = {
    "matches": {
        "id", "session_id", "listing_id", "score", "keyword_score", "semantic_score",
        "matched_skills", "missing_skills", "gap_analysis", "status", "created_at",
    },
    "job_listings": {
        "id", "session_id", "posting_id", "title", "company_name", "source_url", "source_board",
        "description", "requirements_raw", "location", "contract_type", "posted_date",
        "is_expired", "content_hash", "scraped_at",
    },
    "generated_documents": {"id", "match_id", "doc_type", "content", "llm_model", "created_at"},
    "search_sessions": {
        "id", "user_id", "role_title", "status", "preferred_country", "location_pref", "geo_scope",
        "geo_country", "geo_region", "contract_type", "salary_min", "salary_max", "match_threshold",
        "search_mode", "created_at", "last_run_at", "progress_current", "progress_total",
        "progress_message",
    },
}


def _columns(engine, table):
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _digest(engine):
    """Impronta di ogni riga di ogni tabella: serve a provare che non cambia nulla."""
    out = {}
    with engine.connect() as conn:
        tables = [r[0] for r in conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for t in tables:
            rows = conn.exec_driver_sql(f"SELECT * FROM {t} ORDER BY id").fetchall()
            out[t] = {r[0]: hashlib.sha256(repr(tuple(r)).encode()).hexdigest() for r in rows}
    return out


def test_no_new_columns_on_the_tables_candidature_use(orm, db):
    engine = db.get_bind()
    for table, expected in EXPECTED_COLUMNS.items():
        assert _columns(engine, table) == expected, table


def test_saving_only_adds_rows_and_never_rewrites_existing_data(orm, db, api, add_user):
    """Su un database con dati "reali" (ricerche, match, documenti), salvare dal
    feed, cambiare stato e generare documenti aggiunge righe e non ne cambia
    nessuna delle esistenti, salvo lo stato del match che l'utente ha scelto."""
    uid = add_user("a@example.test", ["Python", "SQL"])
    sid, ids = _search_with(orm, db, uid, [
        ("Junior Data Analyst", "Python, SQL", 0.6),
        ("Pflegefachfrau", "Python", 0.6),
    ])
    mt = db.get(orm.models.Match, ids["Junior Data Analyst"])
    db.add(orm.models.GeneratedDocument(match_id=mt.id, doc_type="cv", content="CV esistente"))
    db.commit()

    engine = db.get_bind()
    schema_before = {t: _columns(engine, t) for t in EXPECTED_COLUMNS}
    before = _digest(engine)

    _save(api, uid)                                    # annuncio nuovo dal feed
    _save(api, uid, title="Altro", source_url="https://example.test/altro", status="applied")
    api.get(f"/api/users/{uid}/sessions/{sid}/matches")    # leggere non scrive
    api.get("/api/matches/tracked", params={"user_id": uid})

    after = _digest(engine)
    assert {t: _columns(engine, t) for t in EXPECTED_COLUMNS} == schema_before
    for table, rows in before.items():
        for row_id, digest in rows.items():
            assert after[table].get(row_id) == digest, f"riga modificata o persa: {table}/{row_id}"
    # ...e sono comparse righe nuove: ricerca riservata, 2 annunci, 2 match
    assert len(after["matches"]) == len(before["matches"]) + 2
    assert len(after["search_sessions"]) == len(before["search_sessions"]) + 1


def test_ensure_schema_is_a_no_op_on_a_current_database(orm, db, monkeypatch):
    """ensure_schema (l'unico meccanismo di migrazione all'avvio) non cambia nulla
    su un database già aggiornato, anche rieseguito."""
    database = orm.database
    engine = db.get_bind()
    monkeypatch.setattr(database, "engine", engine)
    before_schema = {t: _columns(engine, t) for t in EXPECTED_COLUMNS}
    before = _digest(engine)
    database.ensure_schema()
    database.ensure_schema()
    assert {t: _columns(engine, t) for t in EXPECTED_COLUMNS} == before_schema
    assert _digest(engine) == before
