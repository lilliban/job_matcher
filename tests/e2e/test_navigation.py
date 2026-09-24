"""Test end-to-end di navigazione fra le 4 view di JobMatcher.

Testa il **comportamento visibile** (non l'implementazione): usa testo dei rail
item + heading di view, così i test sopravvivono a cambi di markup.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.e2e


VIEWS = [
    # (label rail, path route, testo heading unico della view)
    ("Profilo", "/profile", "Chi sei"),
    ("Aziende", "/collections", "Le tue liste di aziende"),
    ("Ricerche", "/sessions", "Cosa cerchi"),
    ("Resoconto", "/intelligence", "Perché è andata così"),
]


def test_home_loads(page, base_url):
    """La homepage carica con rail nav e 4 rail item cliccabili."""
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=15_000)

    # Il testo del logo compare
    assert page.get_by_text("JOBMATCHER").is_visible()

    # I 4 rail item ci sono
    for label, _, _ in VIEWS:
        assert page.get_by_role("link", name=label, exact=False).first.is_visible()


def test_profile_is_default(page, base_url):
    """La view Profilo è quella attiva al boot (redirect / → /profile)."""
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_timeout(600)
    assert page.get_by_role("heading", name="Chi sei").is_visible()


@pytest.mark.parametrize("label,path,heading", VIEWS)
def test_navigate_to_view(page, base_url, label, path, heading):
    """Cliccando il rail item, appare l'heading corretto della view."""
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_timeout(400)

    page.get_by_role("link", name=label, exact=False).first.click()
    page.wait_for_timeout(400)

    assert page.get_by_role("heading", name=heading).is_visible()
    # L'URL riflette la route
    assert path in page.url


def test_rail_active_state_updates(page, base_url):
    """Il rail attivo cambia quando si naviga (React Router aggiunge is-active)."""
    page.goto(base_url, wait_until="networkidle")
    page.wait_for_timeout(400)

    # Click su Ricerche
    page.get_by_role("link", name="Ricerche", exact=False).first.click()
    page.wait_for_timeout(400)

    sessions_link = page.locator('a.rail-item[data-view="sessions"]')
    assert "is-active" in (sessions_link.get_attribute("class") or "")


def test_direct_url_deep_link(page, base_url):
    """Un URL profondo (/intelligence) funziona: React Router riprende dallo stato SPA."""
    page.goto(f"{base_url}/intelligence", wait_until="networkidle")
    page.wait_for_timeout(600)
    assert page.get_by_role("heading", name="Perché è andata così").is_visible()
