"""Smoke test end-to-end del ciclo utente: create → get → patch → delete."""

import uuid


def _unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


def test_user_lifecycle(client, auth_headers):
    # CREATE
    payload = {"name": "Test User", "email": _unique_email("lifecycle")}
    r = client.post("/api/users", headers=auth_headers, json=payload)
    assert r.status_code in (200, 201), r.text
    user = r.json()
    assert user["email"] == payload["email"]
    assert user["name"] == "Test User"
    user_id = user["id"]

    # GET
    r = client.get(f"/api/users/{user_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == user_id

    # PATCH — cambia nome e aggiunge location
    r = client.patch(
        f"/api/users/{user_id}",
        headers=auth_headers,
        json={"name": "Updated Name", "location": "Milano"},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["name"] == "Updated Name"
    assert updated["location"] == "Milano"

    # LIST — deve includerlo
    r = client.get("/api/users", headers=auth_headers)
    assert r.status_code == 200
    ids = [u["id"] for u in r.json()]
    assert user_id in ids

    # DELETE
    r = client.delete(f"/api/users/{user_id}", headers=auth_headers)
    assert r.status_code == 204

    # GET dopo delete → 404
    r = client.get(f"/api/users/{user_id}", headers=auth_headers)
    assert r.status_code == 404


def test_user_soft_skill_flow(client, auth_headers):
    """Verifica che add/list/delete di soft skill funzioni end-to-end."""
    r = client.post(
        "/api/users",
        headers=auth_headers,
        json={"name": "Skill User", "email": _unique_email("skill")},
    )
    assert r.status_code in (200, 201)
    user_id = r.json()["id"]

    # ADD soft skill
    r = client.post(
        f"/api/users/{user_id}/soft-skills",
        headers=auth_headers,
        json={"name": "Comunicazione"},
    )
    assert r.status_code in (200, 201)
    skill = r.json()
    assert skill["name"] == "Comunicazione"

    # LIST — la trova
    r = client.get(f"/api/users/{user_id}/soft-skills", headers=auth_headers)
    assert r.status_code == 200
    names = [s["name"] for s in r.json()]
    assert "Comunicazione" in names


def test_geo_tree_available(client, auth_headers):
    r = client.get("/api/geo", headers=auth_headers)
    assert r.status_code == 200
    tree = r.json()
    # Struttura minima: dict con almeno una country/continent list.
    assert isinstance(tree, dict)
    assert len(tree) > 0


def test_soft_skills_catalog(client, auth_headers):
    r = client.get("/api/skills/soft", headers=auth_headers)
    assert r.status_code == 200
    catalog = r.json()
    assert isinstance(catalog, list)
    assert len(catalog) > 0
    assert all("name" in item for item in catalog)
