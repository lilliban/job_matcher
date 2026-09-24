"""Fixture per test end-to-end Playwright.

Assunzione: uvicorn è già in ascolto su BASE_URL. Se non lo è, i test vengono
saltati con un messaggio esplicativo. Lo script `Claude/scripts/run-regression.ps1`
si occupa di avviare/fermare il server automaticamente.
"""

from __future__ import annotations

import os
import socket

import pytest

BASE_URL = os.environ.get("JM_E2E_BASE_URL", "http://127.0.0.1:8000")


def _server_reachable(url: str) -> bool:
    """Prova a connettersi in TCP (non richiede header di auth)."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_server():
    if not _server_reachable(BASE_URL):
        pytest.skip(
            f"Server non raggiungibile su {BASE_URL}. Avvia uvicorn "
            f"(python run.py) prima di eseguire i test e2e.",
            allow_module_level=True,
        )


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL
