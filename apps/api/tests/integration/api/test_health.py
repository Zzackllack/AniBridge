def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"
    assert "catalog" in r.json()


def test_catalog_health_endpoint(client):
    r = client.get("/health/catalog")
    assert r.status_code == 200
    payload = r.json()
    assert "bootstrap_ready" in payload
    assert "providers" in payload
