"""Test della pipeline di matching: feed finto, database sqlite di prova,
profilo finto. Nessuna chiamata di rete e nessun LLM."""
from unittest.mock import patch

import pytest


def _row(title: str, requirements: str | None, **extra) -> dict:
    return {
        "title": title,
        "company_name": extra.pop("company_name", "Acme"),
        "country_code": extra.pop("country_code", "DE"),
        "requirements_raw": requirements,
        "source_url": f"https://example.test/{title.replace(' ', '-').lower()}",
        "first_seen_at": "2026-11-01T10:00:00",
        **extra,
    }


FEED_ROWS = [
    # priorità 1, copertura 100%
    _row("Junior Data Analyst", "Python, SQL"),
    # priorità 1, copertura 6/9: richieste python/sql/docker/kafka, gradita spark
    _row("Junior Data Engineer", "Python, SQL, Docker, Kafka. Nice to have: Spark"),
    # priorità 1, copertura 0 → resta, below_threshold
    _row("Junior Data Scientist", "Rust, Scala, Kafka"),
    # priorità 1, copertura 50% → resta, below_threshold, prima di quello a 0
    _row("Junior BI Analyst", "Python, Kafka"),
    # priorità 1, nessuna skill riconoscibile → copertura None, non below_threshold
    _row("Junior Business Analyst", "We want a motivated team player."),
    # priorità 3, copertura 25% → resta, below_threshold (messo prima nel feed
    # di quello al 100% per verificare l'ordinamento)
    _row("Junior Backend Developer", "Python, Kafka, Rust, Scala"),
    # priorità 3, copertura 100%
    _row("Junior Software Engineer", "Python and Docker"),
    # priorità 4, requirements_raw vuoto → si usa description
    _row("Junior QA Tester", None, description="Python, SQL"),
    # priorità 5, copertura 25% → resta anche sotto il 60%
    _row("Junior Operations Specialist", "Python, Kafka, Rust, Scala"),
    # priorità 5, copertura 100% → resta
    _row("Junior Platform Specialist", "Python, SQL"),
    # priorità 5, copertura None → scartato
    _row("Office Assistant", "Friendly person for our front desk."),
    # priorità 5, copertura 0 → scartato
    _row("Junior Workplace Coordinator", "Rust, Scala"),
    # scartati dal prefiltro: non tecnico, senior, paese fuori lista, chiuso
    _row("Sales Representative", "Python, SQL"),
    _row("Senior Data Engineer", "Python, SQL"),
    _row("Junior Data Analyst US", "Python, SQL", country_code="US"),
    _row("Junior Data Analyst Closed", "Python, SQL", is_closed=1),
]

# Annunci con paese, modalità e tipo particolari
EXTRA_ROWS = [
    _row("Master Thesis Machine Learning", "Python, SQL"),
    _row("PhD - Data Science for Robots", "Python, Kafka"),
    _row("Junior Data Analyst Unknown", "Python, SQL", country_code=None, location="Hybrid"),
    _row("Junior Data Analyst Europe", "Python, SQL", country_code="GB",
         work_mode="remote", location="Remote, Europe"),
    _row("Junior Data Analyst London", "Python, SQL", country_code="GB",
         work_mode="remote", location="Remote, United Kingdom"),
    _row("Junior Data Analyst Madrid", "Python, SQL", country_code="ES", work_mode="hybrid"),
    _row("Staff Software Engineer, AI Agents", "Python, SQL"),
    _row("Account Executive, Leonardo.ai", "Python, SQL"),
]

USER_SKILLS = ["Python", "SQL", "Docker"]


@pytest.fixture
def run(orm, db, make_feed, tmp_path):
    """run_matching con download_feed sostituito dal feed finto."""
    def _run(user_id, rows=FEED_ROWS):
        feed = make_feed(rows)
        with patch.object(orm.pipeline, "download_feed", return_value=feed) as dl,              patch("subprocess.run", side_effect=AssertionError("nessuna rete nei test")):
            results = orm.pipeline.run_matching(user_id, db, tmp_path / "cache")
        dl.assert_called_once_with(tmp_path / "cache")
        return results
    return _run


# ---------------------------------------------------------------------------
# Lettura del profilo
# ---------------------------------------------------------------------------

def test_load_user_skill_names_reads_profile(orm, db, add_user):
    uid = add_user("a@example.test", USER_SKILLS)
    assert sorted(orm.pipeline.load_user_skill_names(db, uid)) == sorted(USER_SKILLS)


def test_load_user_skill_names_only_that_user(orm, db, add_user):
    add_user("a@example.test", ["Python"])
    uid_b = add_user("b@example.test", ["Rust"])
    assert orm.pipeline.load_user_skill_names(db, uid_b) == ["Rust"]


def test_unknown_user_raises(orm, add_user, run):
    with pytest.raises(ValueError):
        run("non-esiste")


# ---------------------------------------------------------------------------
# run_matching
# ---------------------------------------------------------------------------

def test_run_matching_keeps_and_orders(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    results = run(uid)

    got = [
        (r["title"], r["priority"], r["below_threshold"], r["coverage"])
        for r in results
    ]
    assert got == [
        # sopra soglia: prima 5 skill misurate, poi pochi dati (2 skill)
        ("Junior Data Engineer", 1, False, 0.667),
        ("Junior Data Analyst", 1, False, 1.0),
        # sotto soglia: prima 3 skill misurate, poi pochi dati (2 skill)
        ("Junior Data Scientist", 1, True, 0.0),
        ("Junior BI Analyst", 1, True, 0.5),
        # copertura non misurabile: in coda alla sua priorità
        ("Junior Business Analyst", 1, False, None),
        ("Junior Software Engineer", 3, False, 1.0),
        ("Junior Backend Developer", 3, True, 0.25),
        ("Junior QA Tester", 4, False, 1.0),
        ("Junior Platform Specialist", 5, False, 1.0),
        ("Junior Operations Specialist", 5, True, 0.25),
    ]


def test_run_matching_result_fields(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    results = run(uid)
    by_title = {r["title"]: r for r in results}

    assert by_title["Junior Data Engineer"] == {
        "title": "Junior Data Engineer",
        "company_name": "Acme",
        "country_code": "DE",
        "region": "DE",
        "kind": "job",
        "source_url": "https://example.test/junior-data-engineer",
        "priority": 1,
        "category": "analytics_ai",
        "coverage": 0.667,
        "below_threshold": False,
        "matched_skills": ["docker", "python", "sql"],
        "missing_required": ["kafka"],
        "missing_nice": ["spark"],
        "skills_measured": 5,
        "first_seen_at": "2026-11-01T10:00:00",
        "description": "Python, SQL, Docker, Kafka. Nice to have: Spark",
        "is_new": False,
    }


def test_below_threshold_is_kept_and_flagged(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    by_title = {r["title"]: r for r in run(uid)}

    zero = by_title["Junior Data Scientist"]
    assert zero["coverage"] == 0.0
    assert zero["below_threshold"] is True
    assert zero["missing_required"] == ["kafka", "rust", "scala"]

    half = by_title["Junior BI Analyst"]
    assert half["coverage"] == 0.5
    assert half["below_threshold"] is True


def test_below_threshold_false_at_or_above_threshold(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    by_title = {r["title"]: r for r in run(uid)}
    assert by_title["Junior Data Analyst"]["below_threshold"] is False
    assert by_title["Junior Data Engineer"]["below_threshold"] is False


def test_below_threshold_sorted_after_others_within_priority(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    results = run(uid)
    # tra le coperture misurate; quelle non misurabili stanno in coda
    for priority in {r["priority"] for r in results}:
        flags = [
            r["below_threshold"] for r in results
            if r["priority"] == priority and r["coverage"] is not None
        ]
        assert flags == sorted(flags), f"priorità {priority}: {flags}"


def test_prefilter_discards_are_dropped(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    titles = {r["title"] for r in run(uid)}
    assert not titles & {
        "Sales Representative",
        "Senior Data Engineer",
        "Junior Data Analyst US",
        "Junior Data Analyst Closed",
    }


def test_priority5_needs_measured_coverage(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    results = run(uid)
    p5 = [(r["title"], r["coverage"]) for r in results if r["priority"] == 5]
    # "Office Assistant" (copertura None) e "Junior Workplace Coordinator"
    # (copertura 0) sono scartati; il 25% resta: per la priorità 5 non c'è
    # la soglia del 60%, basta una copertura misurata e maggiore di zero.
    assert p5 == [
        ("Junior Platform Specialist", 1.0),
        ("Junior Operations Specialist", 0.25),
    ]


def test_none_coverage_kept_for_classified_roles(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    results = run(uid)
    ba = next(r for r in results if r["title"] == "Junior Business Analyst")
    assert ba["coverage"] is None
    assert ba["below_threshold"] is False
    assert ba["matched_skills"] == []


def test_description_used_when_requirements_missing(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    results = run(uid)
    qa = next(r for r in results if r["title"] == "Junior QA Tester")
    assert qa["matched_skills"] == ["python", "sql"]


def test_profile_without_skills(orm, add_user, run):
    """Senza skill ogni copertura misurata è 0: i ruoli classificati restano
    tutti marcati below_threshold, quelli di priorità 5 spariscono. A pari
    copertura (0%) gli annunci con meno di 3 skill misurate vanno dopo."""
    uid = add_user("vuoto@example.test", [])
    results = run(uid)

    assert [(r["title"], r["priority"], r["below_threshold"]) for r in results] == [
        ("Junior Data Engineer", 1, True),
        ("Junior Data Scientist", 1, True),
        ("Junior Data Analyst", 1, True),
        ("Junior BI Analyst", 1, True),
        ("Junior Business Analyst", 1, False),
        ("Junior Backend Developer", 3, True),
        ("Junior Software Engineer", 3, True),
        ("Junior QA Tester", 4, True),
    ]


def test_empty_feed_returns_empty_list(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    assert run(uid, rows=[]) == []


def test_no_llm_call(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    with patch(
        "app.services.llm_gateway.LLMGateway.complete_json",
        side_effect=AssertionError("la pipeline non deve usare l'LLM"),
    ):
        assert run(uid)


# ---------------------------------------------------------------------------
# Copertura non misurabile, tesi, paesi
# ---------------------------------------------------------------------------

def test_unmeasurable_coverage_sorted_after_measured_in_same_priority(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    results = run(uid)
    for priority in {r["priority"] for r in results}:
        unmeasured = [r["coverage"] is None for r in results if r["priority"] == priority]
        assert unmeasured == sorted(unmeasured), f"priorità {priority}: {unmeasured}"
    p1 = [r["title"] for r in results if r["priority"] == 1]
    assert p1[-1] == "Junior Business Analyst"


def test_thesis_is_kept_and_marked(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    by_title = {r["title"]: r for r in run(uid, rows=FEED_ROWS + EXTRA_ROWS)}
    assert by_title["Master Thesis Machine Learning"]["kind"] == "thesis"
    assert by_title["PhD - Data Science for Robots"]["kind"] == "thesis"
    assert by_title["Junior Data Analyst"]["kind"] == "job"
    jobs = [r for r in by_title.values() if r["kind"] == "job"]
    assert not any("Thesis" in r["title"] or "PhD" in r["title"] for r in jobs)


def test_regions_in_results(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    by_title = {r["title"]: r for r in run(uid, rows=FEED_ROWS + EXTRA_ROWS)}

    unknown = by_title["Junior Data Analyst Unknown"]
    assert unknown["country_code"] is None
    assert unknown["region"] == "unknown"

    assert by_title["Junior Data Analyst Europe"]["region"] == "remote_eu"
    assert by_title["Junior Data Analyst"]["region"] == "DE"
    # Regno Unito e Spagna fuori, anche se da remoto
    assert "Junior Data Analyst London" not in by_title
    assert "Junior Data Analyst Madrid" not in by_title
    assert {r["region"] for r in by_title.values()} <= {"CH", "DE", "NL", "remote_eu", "unknown"}


def test_wrong_roles_are_not_in_results(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    titles = {r["title"] for r in run(uid, rows=FEED_ROWS + EXTRA_ROWS)}
    assert "Staff Software Engineer, AI Agents" not in titles
    assert "Account Executive, Leonardo.ai" not in titles


# ---------------------------------------------------------------------------
# Pochi dati: percentuali calcolate su 1-2 skill
# ---------------------------------------------------------------------------

def test_skills_measured_counts_required_and_nice(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    by_title = {r["title"]: r for r in run(uid)}
    assert by_title["Junior Data Analyst"]["skills_measured"] == 2
    # python, sql, docker, kafka richieste + spark gradita
    assert by_title["Junior Data Engineer"]["skills_measured"] == 5
    # copertura non misurabile: nessuna skill trovata
    assert by_title["Junior Business Analyst"]["skills_measured"] == 0


def test_few_skills_not_above_many_at_similar_coverage(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    rows = [
        # 1 di 1 skill: 100%, ma su un solo dato
        _row("Junior Data Analyst One", "Python"),
        # 4 skill misurate (3 richieste + 1 gradita), 6/7 = 85,7%
        _row("Junior Data Analyst Four", "Python, SQL and Docker. Nice to have: Kafka"),
    ]
    got = [(r["title"], r["coverage"], r["skills_measured"]) for r in run(uid, rows)]
    assert got == [
        ("Junior Data Analyst Four", 0.857, 4),
        ("Junior Data Analyst One", 1.0, 1),
    ]


def test_low_data_not_buried_under_rich_below_threshold(orm, add_user, run):
    """La fascia di soglia pesa più dei pochi dati: un 100% su due skill
    resta davanti a un 50% su quattro."""
    uid = add_user("a@example.test", USER_SKILLS)
    rows = [
        # 4 skill misurate, 2/4 = 50% (sotto soglia)
        _row("Junior Data Analyst Half", "Python, SQL, Kafka, Rust"),
        # 2 di 2 skill: 100%, pochi dati
        _row("Junior Data Analyst Two", "Python, SQL"),
    ]
    titles = [r["title"] for r in run(uid, rows)]
    assert titles == ["Junior Data Analyst Two", "Junior Data Analyst Half"]


def test_enough_skills_first_within_band(orm, add_user, run):
    """Sopra soglia: chi ha almeno 3 skill misurate viene prima anche se il
    pochi dati ha una percentuale più alta."""
    uid = add_user("a@example.test", USER_SKILLS)
    rows = [
        _row("Junior Data Analyst One", "Python"),                         # 1 di 1: 100%
        _row("Junior Data Analyst Four", "Python, SQL and Docker. Nice to have: Kafka"),  # 85,7%
    ]
    got = [(r["title"], r["below_threshold"], r["skills_measured"]) for r in run(uid, rows)]
    assert got == [
        ("Junior Data Analyst Four", False, 4),
        ("Junior Data Analyst One", False, 1),
    ]


def test_low_data_stays_visible_before_unmeasured(orm, add_user, run):
    """Pochi dati: dopo chi ha più skill, ma prima delle coperture non
    misurabili, e mai tolti dalla lista."""
    uid = add_user("a@example.test", USER_SKILLS)
    rows = [
        _row("Junior Data Analyst None", "Excel and PowerPoint"),       # nessuna skill riconosciuta
        _row("Junior Data Analyst One", "Python"),                      # 1 di 1
        _row("Junior Data Analyst Four", "Python, SQL and Docker. Nice to have: Kafka"),  # 4 skill, 85,7%
    ]
    got = [(r["title"], r["skills_measured"]) for r in run(uid, rows)]
    titles = [t for t, _ in got]
    assert titles.index("Junior Data Analyst Four") < titles.index("Junior Data Analyst One")
    assert "Junior Data Analyst One" in titles
    if "Junior Data Analyst None" in titles:
        assert titles.index("Junior Data Analyst One") < titles.index("Junior Data Analyst None")


def test_low_data_group_sorted_by_threshold_then_coverage(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    rows = [
        _row("Junior Data Analyst Half Two", "Python, Rust"),   # 1 di 2: 50%, sotto soglia
        _row("Junior Data Analyst One", "Python"),              # 1 di 1: 100%
    ]
    titles = [r["title"] for r in run(uid, rows)]
    assert titles == ["Junior Data Analyst One", "Junior Data Analyst Half Two"]


def test_few_skills_does_not_jump_priority(orm, add_user, run):
    uid = add_user("a@example.test", USER_SKILLS)
    rows = [
        _row("Junior Software Engineer", "Python, SQL, Docker, Kafka"),  # priorità 3
        _row("Junior Data Analyst One", "Python"),                        # priorità 1
    ]
    got = [(r["title"], r["priority"]) for r in run(uid, rows)]
    assert got == [("Junior Data Analyst One", 1), ("Junior Software Engineer", 3)]
