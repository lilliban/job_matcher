"""Ultimo test della suite (il nome lo mette in coda): i database reali non devono
essere cambiati da nessun test, e DATABASE_URL deve puntare a un file temporaneo.

Se fallisce con "modificato" mentre usi l'app sulla porta 8000, può essere l'app
stessa a scrivere nel database: ripeti la suite a backend fermo."""
import importlib
from pathlib import Path


def _conftest():
    return importlib.import_module("conftest")


def test_database_url_points_to_a_scratch_file_not_the_real_one():
    config = importlib.import_module("app.core.config")
    real = _conftest().PROJECT_ROOT / "job_matcher.db"
    url = config.DATABASE_URL
    assert url.startswith("sqlite:///")
    path = Path(url.removeprefix("sqlite:///"))
    assert path.resolve() != real.resolve()
    assert "jobmatcher-tests-" in path.as_posix()


def test_real_databases_were_not_touched_by_the_suite():
    c = _conftest()
    for path, before in c._REAL_FINGERPRINTS.items():
        assert c._fingerprint(path) == before, f"{path.name}: modificato durante i test"
