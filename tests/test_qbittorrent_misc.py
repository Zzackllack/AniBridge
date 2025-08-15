def test_misc_endpoints(client):
    r = client.post("/api/v2/auth/logout")
    assert r.status_code == 200

    assert client.get("/api/v2/app/version").text == "4.6.0"
    assert client.get("/api/v2/app/webapiVersion").text == "2.8.18"

    bi = client.get("/api/v2/app/buildInfo").json()
    assert "openssl" in bi

    tr = client.get("/api/v2/transfer/info").json()
    assert "dl_info_speed" in tr
