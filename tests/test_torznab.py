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
        lambda series_title, season, episode, height, vcodec, language, site="aniworld.to": (
            "Title"
        ),
    )
    monkeypatch.setattr(
        tn,
        "build_magnet",
        lambda title, slug, season, episode, language, provider, site="aniworld.to", **_kwargs: (
            "magnet:?xt=urn:btih:test&dn=Title&aw_slug=slug&aw_s=1&aw_e=1&aw_lang=German+Sub&aw_site=aniworld.to"
        ),
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


def test_tvsearch_uses_id_resolved_query_when_q_missing(client, monkeypatch):
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api_mod

    class Rec:
        available = True
        is_fresh = True
        height = 1080
        vcodec = "h264"
        provider = "prov"

    seen = {"query": None}

    def _slug_from_query(query, site=None):
        """
        Record the provided query in the shared `seen` mapping and return a fixed (site, slug) pair.

        Parameters:
            query (str): The query string to record.
            site (str | None): Optional site hint (unused by this stub).

        Returns:
            tuple: A two-element tuple (site, slug) where `site` is `"aniworld.to"` and `slug` is `"slug"`.

        Side effects:
            Mutates the `seen` mapping by setting `seen["query"] = query`.
        """
        seen["query"] = query
        return ("aniworld.to", "slug")

    monkeypatch.setattr(
        torznab_api_mod,
        "_resolve_tvsearch_query_from_ids",
        lambda **_kwargs: "The Rookie",
    )
    monkeypatch.setattr(tn, "_slug_from_query", _slug_from_query)
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
        lambda series_title, season, episode, height, vcodec, language, site="aniworld.to": (
            "Title"
        ),
    )
    monkeypatch.setattr(
        tn,
        "build_magnet",
        lambda title, slug, season, episode, language, provider, site="aniworld.to", **_kwargs: (
            "magnet:?xt=urn:btih:test&dn=Title&aw_slug=slug&aw_s=1&aw_e=1&aw_lang=German+Sub&aw_site=aniworld.to"
        ),
    )

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "season": 1, "ep": 1, "tvdbid": 350665},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    assert root.find("./channel/item") is not None
    assert seen["query"] == "The Rookie"


def test_tvsearch_season_search_emits_multiple_episodes(client, monkeypatch):
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api_mod

    class Rec:
        available = True
        is_fresh = True
        height = 1080
        vcodec = "h264"
        provider = "prov"

    monkeypatch.setattr(
        tn, "_slug_from_query", lambda q, site=None: ("aniworld.to", "slug")
    )
    monkeypatch.setattr(
        tn, "resolve_series_title", lambda slug, site="aniworld.to": "Series"
    )
    monkeypatch.setattr(
        torznab_api_mod, "_metadata_episode_numbers_for_season", lambda **_kwargs: []
    )
    monkeypatch.setattr(torznab_api_mod, "STRM_FILES_MODE", "no")
    monkeypatch.setattr(
        tn,
        "list_cached_episode_numbers_for_season",
        lambda session, slug, season, site="aniworld.to": [1, 2, 3],
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
    monkeypatch.setattr(tn, "upsert_availability", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tn,
        "build_release_name",
        lambda series_title, season, episode, height, vcodec, language, site="aniworld.to": (
            f"Title S{int(season):02d}E{int(episode):02d}"
        ),
    )
    monkeypatch.setattr(
        tn,
        "build_magnet",
        lambda title, slug, season, episode, language, provider, site="aniworld.to", **_kwargs: (
            f"magnet:?xt=urn:btih:test&dn=Title&aw_slug={slug}&aw_s={season}&aw_e={episode}&aw_lang=German+Sub&aw_site={site}"
        ),
    )

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 3
    urls = [
        (
            item.find("enclosure").get("url")
            if item.find("enclosure") is not None
            else ""
        )
        for item in items
    ]
    assert any("aw_e=1" in url for url in urls)
    assert any("aw_e=2" in url for url in urls)
    assert any("aw_e=3" in url for url in urls)


def test_tvsearch_season_search_fallback_stops_on_consecutive_misses(
    client, monkeypatch
):
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api_mod

    class Rec:
        def __init__(self, height=1080, vcodec="h264", provider="VOE"):
            self.available = True
            self.is_fresh = True
            self.height = height
            self.vcodec = vcodec
            self.provider = provider

    monkeypatch.setattr(
        tn, "_slug_from_query", lambda q, site=None: ("aniworld.to", "slug")
    )
    monkeypatch.setattr(
        tn, "resolve_series_title", lambda slug, site="aniworld.to": "Series"
    )
    monkeypatch.setattr(
        torznab_api_mod, "_metadata_episode_numbers_for_season", lambda **_kwargs: []
    )
    monkeypatch.setattr(torznab_api_mod, "STRM_FILES_MODE", "no")
    monkeypatch.setattr(
        tn,
        "list_cached_episode_numbers_for_season",
        lambda session, slug, season, site="aniworld.to": [],
    )
    monkeypatch.setattr(
        tn,
        "list_available_languages_cached",
        lambda session, slug, season, episode, site="aniworld.to": ["German Sub"],
    )

    cached: dict[tuple[int, int, str], Rec] = {}

    def _get_availability(session, slug, season, episode, language, site="aniworld.to"):
        _ = (session, slug, site)
        return cached.get((season, episode, language))

    monkeypatch.setattr(tn, "get_availability", _get_availability)

    probe_calls: list[int] = []

    def _probe_quality(slug, season, episode, language, site="aniworld.to", **_kwargs):
        _ = (slug, language, site)
        probe_calls.append(episode)
        if episode in (1, 2):
            return (True, 1080, "h264", "VOE", {})
        return (False, None, None, None, None)

    monkeypatch.setattr(tn, "probe_episode_quality", _probe_quality)

    def _upsert_availability(
        session,
        slug,
        season,
        episode,
        language,
        available,
        height=None,
        vcodec=None,
        provider=None,
        extra=None,
        site="aniworld.to",
    ):
        _ = (session, slug, extra, site)
        if available:
            cached[(season, episode, language)] = Rec(height, vcodec, provider)

    monkeypatch.setattr(tn, "upsert_availability", _upsert_availability)
    monkeypatch.setattr(
        tn,
        "build_release_name",
        lambda series_title, season, episode, height, vcodec, language, site="aniworld.to": (
            f"Title S{int(season):02d}E{int(episode):02d}"
        ),
    )
    monkeypatch.setattr(
        tn,
        "build_magnet",
        lambda title, slug, season, episode, language, provider, site="aniworld.to", **_kwargs: (
            f"magnet:?xt=urn:btih:test&dn=Title&aw_slug={slug}&aw_s={season}&aw_e={episode}&aw_lang=German+Sub&aw_site={site}"
        ),
    )

    monkeypatch.setattr(torznab_api_mod, "TORZNAB_SEASON_SEARCH_MAX_EPISODES", 10)
    monkeypatch.setattr(
        torznab_api_mod, "TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES", 2
    )

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 2
    assert probe_calls == [1, 2, 3, 4]


def test_tvsearch_season_search_limit_is_hard_item_cap(client, monkeypatch):
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api_mod

    class Rec:
        available = True
        is_fresh = True
        height = 1080
        vcodec = "h264"
        provider = "prov"

    monkeypatch.setattr(
        tn, "_slug_from_query", lambda q, site=None: ("aniworld.to", "slug")
    )
    monkeypatch.setattr(
        tn, "resolve_series_title", lambda slug, site="aniworld.to": "Series"
    )
    monkeypatch.setattr(
        torznab_api_mod, "_metadata_episode_numbers_for_season", lambda **_kwargs: []
    )
    monkeypatch.setattr(
        tn,
        "list_cached_episode_numbers_for_season",
        lambda session, slug, season, site="aniworld.to": [1, 2],
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
    monkeypatch.setattr(tn, "upsert_availability", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        tn,
        "build_release_name",
        lambda series_title, season, episode, height, vcodec, language, site="aniworld.to": (
            f"Title S{int(season):02d}E{int(episode):02d}"
        ),
    )
    monkeypatch.setattr(
        tn,
        "build_magnet",
        lambda title, slug, season, episode, language, provider, site="aniworld.to", **_kwargs: (
            f"magnet:?xt=urn:btih:test&dn=Title&aw_slug={slug}&aw_s={season}&aw_e={episode}&aw_lang=German+Sub&aw_site={site}"
        ),
    )
    monkeypatch.setattr(torznab_api_mod, "STRM_FILES_MODE", "both")

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "foo", "season": 1, "limit": 3},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    items = root.findall("./channel/item")
    assert len(items) == 3
