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

    # Return (site, slug) tuple for new multi-site API
    monkeypatch.setattr(
        tn, "_slug_from_query", lambda q, site=None: ("aniworld.to", "slug")
    )
    monkeypatch.setattr(
        tn, "resolve_series_title", lambda slug, site="aniworld.to": "Series"
    )
    monkeypatch.setattr(
        tn,
        "list_available_languages_cached",
        lambda session, slug, season, episode, site="aniworld.to": ["German Sub"],
    )
    monkeypatch.setattr(
        tn,
        "get_availability",
        lambda session, slug, season, episode, language, site="aniworld.to": Rec(),
    )
    monkeypatch.setattr(
        tn,
        "build_release_name",
        lambda series_title,
        season,
        episode,
        height,
        vcodec,
        language,
        site="aniworld.to": "Title",
    )
    monkeypatch.setattr(
        tn,
        "build_magnet",
        lambda title,
        slug,
        season,
        episode,
        language,
        provider,
        site="aniworld.to",
        **_kwargs: "magnet:?xt=urn:btih:test&dn=Title&aw_slug=slug&aw_s=1&aw_e=1&aw_lang=German+Sub&aw_site=aniworld.to",
    )

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
    lang_attr = item.find(
        "{http://torznab.com/schemas/2015/feed}attr[@name='language']"
    )
    subs_attr = item.find("{http://torznab.com/schemas/2015/feed}attr[@name='subs']")
    assert seed is not None and leech is not None
    assert lang_attr is not None and lang_attr.get("value") == "German"
    assert subs_attr is not None and subs_attr.get("value") == "German"


def test_tvsearch_empty(client):
    resp = client.get("/torznab/api", params={"t": "tvsearch", "q": "foo"})
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    assert root.find("./channel/item") is None
