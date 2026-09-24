"""Smoke test dell'endpoint di health e della configurazione di boot."""


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["llm_primary"] in {"gemini", "ollama"}
    assert isinstance(body["places_enabled"], bool)


def test_openapi_available(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "JobMatcher API"
    # Sanity check: alcuni router chiave sono registrati.
    paths = schema["paths"]
    assert "/api/health" in paths
    assert any(p.startswith("/api/users") for p in paths)
    assert any(p.startswith("/api/geo") for p in paths)


def test_missing_token_rejected(client):
    """Endpoint protetti richiedono `X-API-Token`."""
    # Cerchiamo un utente inesistente: senza token → 401, con token → 404.
    r = client.get("/api/users/999999")
    assert r.status_code == 401


def test_invalid_token_rejected(client):
    r = client.get("/api/users/999999", headers={"X-API-Token": "wrong"})
    assert r.status_code == 401
