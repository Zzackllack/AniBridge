def test_torznab_unknown_t_returns_400(client):
    r = client.get("/torznab/api", params={"t": "unknown"})
    assert r.status_code == 400


def test_torznab_tvsearch_missing_params_returns_empty_rss(client):
    r = client.get("/torznab/api", params={"t": "tvsearch", "q": "foo"})
    assert r.status_code == 200
    assert "<rss" in r.text
