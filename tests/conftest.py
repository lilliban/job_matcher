"""Configurazione pytest condivisa: fixture per TestClient e DB isolato."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Configura l'ambiente PRIMA di importare l'app, così `app.core.config`
# legge i valori giusti.
_TEST_DB_PATH = Path(tempfile.gettempdir()) / "jm-test.db"
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB_PATH}")
os.environ.setdefault("API_TOKEN", "test-token")

# Rende `app.*` importabile anche se pytest viene lanciato da qualsiasi cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    """Crea uno schema DB pulito per la sessione di test."""
    if _TEST_DB_PATH.exists():
        _TEST_DB_PATH.unlink()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Su Windows il file SQLite resta lockato finché l'engine non viene chiuso.
    engine.dispose()
    if _TEST_DB_PATH.exists():
        try:
            _TEST_DB_PATH.unlink()
        except PermissionError:
            pass  # meglio un file temp orfano che un teardown fallito


@pytest.fixture
def client() -> TestClient:
    """TestClient FastAPI con lifespan attivo (create_all viene rieseguito)."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Header `X-API-Token` con il valore di test."""
    return {"X-API-Token": "test-token"}
