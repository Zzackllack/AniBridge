def test_login_and_basic_endpoints(client):
    resp = client.post("/api/v2/auth/login", data={"username": "u", "password": "p"})
    assert resp.status_code == 200
    assert resp.cookies.get("SID") == "anibridge"

    pref = client.get("/api/v2/app/preferences")
    assert pref.status_code == 200
    assert "save_path" in pref.json()

    cats = client.get("/api/v2/torrents/categories")
    assert cats.status_code == 200
    assert "prowlarr" in cats.json()
