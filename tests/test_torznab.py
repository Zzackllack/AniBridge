import xml.etree.ElementTree as ET


def test_caps(client):
    resp = client.get("/torznab/api", params={"t": "caps"})
    assert resp.status_code == 200
    ET.fromstring(resp.text)


def test_search(client):
    resp = client.get("/torznab/api", params={"t": "search", "q": "test"})
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    assert root.find("channel") is not None


def test_tvsearch_happy_path(client, monkeypatch):
    import app.api.torznab as tn

    class Rec:
        available = True
        is_fresh = True
        height = 1080
        vcodec = "h264"
        provider = "prov"

    monkeypatch.setattr(tn, "_slug_from_query", lambda q: "slug")
    monkeypatch.setattr(tn, "resolve_series_title", lambda slug: "Series")
    monkeypatch.setattr(
        tn,
        "list_available_languages_cached",
        lambda session, slug, season, episode: ["German Dub"],
    )
    monkeypatch.setattr(
        tn,
        "get_availability",
        lambda session, slug, season, episode, language: Rec(),
    )
    def fake_build_release_name(
        *,
        series_title,
        season,
        episode,
        absolute_number=None,
        height=None,
        vcodec=None,
        language,
    ):
        return "Title"

    def fake_build_magnet(
        *,
        title,
        slug,
        season,
        episode,
        language,
        provider=None,
        absolute_number=None,
    ):
        return "magnet:?xt=urn:btih:test&dn=Title&aw_slug=slug&aw_s=1&aw_e=1&aw_lang=German+Dub"

    monkeypatch.setattr(tn, "build_release_name", fake_build_release_name)
    monkeypatch.setattr(tn, "build_magnet", fake_build_magnet)

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1, "ep": 1},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    item = root.find("./channel/item")
    assert item is not None
    seed = item.find("{http://torznab.com/schemas/2015/feed}attr[@name='seeders']")
    leech = item.find("{http://torznab.com/schemas/2015/feed}attr[@name='leechers']")
    assert seed is not None and leech is not None


def test_tvsearch_empty(client):
    resp = client.get("/torznab/api", params={"t": "tvsearch", "q": "foo"})
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    assert root.find("./channel/item") is None
