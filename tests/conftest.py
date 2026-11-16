"""Stub heavy optional dependencies so pure-function tests run without extras."""
import hashlib
import importlib
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Nessun test deve scrivere sui database reali.
#
# `app.core.config` legge DATABASE_URL all'importazione (e load_dotenv non
# sovrascrive una variabile già impostata): la punto a un file temporaneo PRIMA
# che qualunque modulo dell'app venga importato. Così anche un test che
# dimenticasse di sostituire `get_db` troverebbe un database vuoto e usa-e-getta,
# non job_matcher.db.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_FILES = (PROJECT_ROOT / "job_matcher.db", PROJECT_ROOT / "feeds_cache" / "jobs.sqlite")
_SCRATCH_DIR = tempfile.mkdtemp(prefix="jobmatcher-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_SCRATCH_DIR, 'tests.db').as_posix()}"


def _fingerprint(path: Path):
    """(dimensione, data di modifica, sha256 per i file piccoli) o None se manca."""
    if not path.exists():
        return None
    st = path.stat()
    digest = None
    if st.st_size < 50 * 1024 * 1024:  # il feed da ~240 MB si confronta solo per dimensione e data
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return (st.st_size, st.st_mtime_ns, digest)


_REAL_FINGERPRINTS = {p: _fingerprint(p) for p in REAL_FILES}

for _mod in [
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.exc",
    "httpx",
]:
    sys.modules.setdefault(_mod, MagicMock())


# ---------------------------------------------------------------------------
# Fixture per i test che hanno bisogno di un database vero
# ---------------------------------------------------------------------------

# Moduli stubbati sopra, più quelli dell'app che ne dipendono: dentro la
# fixture `orm` vengono sostituiti con le versioni reali.
_REAL_PREFIXES = (
    "sqlalchemy",
    "httpx",
    "starlette.testclient",
    "fastapi.testclient",
    "app.database",
    "app.models",
    "app.routers",
    # tutti i servizi: alcuni (search_runner, llm_gateway, application_builder...)
    # importano sqlalchemy, e se un altro modulo di test li ha caricati con lo
    # stub resterebbero legati a un MagicMock
    "app.services",
)

# Moduli reali già importati da un modulo di test precedente: si riusano
# invece di reimportarli (sqlalchemy non va eseguito due volte).
_real_modules: dict = {}


def _is_real(name: str) -> bool:
    return any(name == p or name.startswith(p + ".") for p in _REAL_PREFIXES)


def _relink_parents() -> None:
    """Riallinea gli attributi dei pacchetti ai moduli reali in sys.modules.

    `from app import models` e `from app.services import tracking` leggono
    l'ATTRIBUTO del pacchetto, non sys.modules. Alla fine di un modulo di test
    quegli attributi tornano ai moduli "stubbati" di prima; al modulo successivo
    sys.modules ha di nuovo i moduli reali, ma i pacchetti puntano ancora ai
    vecchi: un router importato per la prima volta lì si legava a un MagicMock."""
    for name, mod in list(sys.modules.items()):
        if _is_real(name):
            parent, _, child = name.rpartition(".")
            if parent in sys.modules:
                setattr(sys.modules[parent], child, mod)


@pytest.fixture(scope="module")
def orm():
    """sqlalchemy e httpx veri al posto dei MagicMock, solo per il modulo di
    test che la richiede. Alla fine sys.modules torna com'era, così i test
    che contano sugli stub non cambiano comportamento."""
    saved = dict(sys.modules)
    for name in list(sys.modules):
        if _is_real(name):
            del sys.modules[name]
    sys.modules.update(_real_modules)
    _relink_parents()
    try:
        sqlalchemy = importlib.import_module("sqlalchemy")
        sa_orm = importlib.import_module("sqlalchemy.orm")
        database = importlib.import_module("app.database")
        models = importlib.import_module("app.models")
        pipeline = importlib.import_module("app.services.pipeline")
        yield SimpleNamespace(
            create_engine=sqlalchemy.create_engine,
            sessionmaker=sa_orm.sessionmaker,
            database=database,
            Base=database.Base,
            models=models,
            pipeline=pipeline,
        )
    finally:
        for name, mod in list(sys.modules.items()):
            if _is_real(name):
                _real_modules[name] = mod
                del sys.modules[name]
        sys.modules.update({n: m for n, m in saved.items() if _is_real(n)})
        for name, mod in saved.items():
            parent, _, child = name.rpartition(".")
            if parent in saved and _is_real(name):
                setattr(saved[parent], child, mod)


@pytest.fixture
def db(orm, tmp_path):
    """Database applicativo di prova: sqlite su file, schema reale."""
    engine = orm.create_engine(
        f"sqlite:///{(tmp_path / 'app.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    orm.Base.metadata.create_all(engine)
    session = orm.sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def add_user(orm, db):
    """Crea un profilo finto con le hard skill date e ne ritorna l'id."""
    def _add(email: str, skills: list[str]) -> str:
        user = orm.models.User(name="Profilo Finto", email=email)
        for name in skills:
            user.hard_skills.append(orm.models.UserHardSkill(name=name))
        db.add(user)
        db.commit()
        return user.id
    return _add


@pytest.fixture
def make_feed(tmp_path):
    """Crea un mini-feed con la stessa tabella postings letta da load_postings."""
    from app.services.feed_reader import POSTING_COLUMNS

    def _make(rows: list[dict], name: str = "jobs.sqlite"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        cols_def = ", ".join(f"{c} TEXT" for c in POSTING_COLUMNS) + ", is_closed INTEGER DEFAULT 0"
        conn.execute(f"CREATE TABLE postings ({cols_def})")
        placeholders = ", ".join("?" for _ in range(len(POSTING_COLUMNS) + 1))
        for row in rows:
            vals = [row.get(c) for c in POSTING_COLUMNS] + [row.get("is_closed", 0)]
            conn.execute(f"INSERT INTO postings VALUES ({placeholders})", vals)
        conn.commit()
        conn.close()
        return path
    return _make
