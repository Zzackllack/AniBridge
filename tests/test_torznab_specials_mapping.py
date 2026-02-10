import xml.etree.ElementTree as ET


def _fake_release_name(
    series_title,
    season,
    episode,
    height,
    vcodec,
    language,
    site="aniworld.to",
):
    """
    Constructs a fake release name for a series episode using the provided season and episode numbers.

    Parameters:
        series_title (str): Ignored; present for signature compatibility.
        season (int): Season number; used and zero-padded to two digits in the result.
        episode (int): Episode number; used and zero-padded to two digits in the result.
        height (int): Ignored; present for signature compatibility.
        vcodec (str): Ignored; present for signature compatibility.
        language (str): Ignored; present for signature compatibility.
        site (str): Ignored; present for signature compatibility.

    Returns:
        str: A release-name string in the form "Kaguya.SXXEYY.1080p.WEB.H264.GER.SUB-ANIWORLD"
             where XX is the zero-padded season and YY is the zero-padded episode.
    """
    _ = (series_title, height, vcodec, language, site)
    return (
        f"Kaguya.S{int(season):02d}E{int(episode):02d}.1080p.WEB.H264.GER.SUB-ANIWORLD"
    )


def _fake_magnet(
    title,
    slug,
    season,
    episode,
    language,
    provider,
    site="aniworld.to",
    **_kwargs,
):
    """
    Builds a fake magnet URI that encodes the provided slug, season, episode, and site as aw_* query parameters.

    Parameters:
        slug (str): Series slug to include as the `aw_slug` query parameter.
        season (int): Season index to include as the `aw_s` query parameter.
        episode (int): Episode index to include as the `aw_e` query parameter.
        site (str): Site identifier to include as the `aw_site` query parameter (default "aniworld.to").

    Returns:
        str: A magnet URI string containing `aw_slug`, `aw_s`, `aw_e`, and `aw_site` set to the provided values.
    """
    _ = (title, language, provider)
    return (
        f"magnet:?xt=urn:btih:test&dn=Kaguya"
        f"&aw_slug={slug}&aw_s={season}&aw_e={episode}&aw_site={site}"
    )


def test_search_uses_special_mapping_alias_in_title(client, monkeypatch):
    """
    Verify that a torznab search result applies a special episode mapping alias to the item title and enclosure parameters.

    Performs a search request and asserts a 200 response, that an item exists whose title contains "S00E05", and that the enclosure URL includes "aw_s=0" and "aw_e=4".
    """
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api
    from app.providers.aniworld.specials import SpecialEpisodeMapping

    monkeypatch.setattr(torznab_api, "ANIBRIDGE_TEST_MODE", False)
    monkeypatch.setattr(
        tn, "_slug_from_query", lambda q, site=None: ("aniworld.to", "kaguya")
    )
    monkeypatch.setattr(
        tn, "resolve_series_title", lambda slug, site="aniworld.to": "Kaguya-sama"
    )
    monkeypatch.setattr(
        torznab_api,
        "resolve_special_mapping_from_query",
        lambda **_kwargs: SpecialEpisodeMapping(
            source_season=0,
            source_episode=4,
            alias_season=0,
            alias_episode=5,
            metadata_title="special title",
            metadata_tvdb_id=12345,
        ),
    )
    monkeypatch.setattr(
        tn,
        "list_available_languages_cached",
        lambda session, slug, season, episode, site="aniworld.to": ["German Sub"],
    )
    monkeypatch.setattr(
        tn,
        "probe_episode_quality",
        lambda **_kwargs: (True, 1080, "h264", "VOE", {}),
    )
    monkeypatch.setattr(tn, "upsert_availability", lambda *args, **kwargs: None)
    monkeypatch.setattr(tn, "build_release_name", _fake_release_name)
    monkeypatch.setattr(tn, "build_magnet", _fake_magnet)

    resp = client.get(
        "/torznab/api",
        params={"t": "search", "q": "Kaguya special title", "cat": "5070"},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    item = root.find("./channel/item")
    assert item is not None
    title = item.findtext("title") or ""
    assert "S00E05" in title
    enclosure = item.find("enclosure")
    assert enclosure is not None
    url = enclosure.get("url") or ""
    assert "aw_s=0" in url
    assert "aw_e=4" in url


def test_tvsearch_falls_back_to_special_mapping_when_requested_episode_missing(
    client,
    monkeypatch,
):
    """
    Verifies that a tvsearch request falls back to a SpecialEpisodeMapping when the requested episode is unavailable and that the resulting item reflects the alias episode and mapped source.

    Asserts the response contains an item whose title includes "S00E05" (the alias episode) and whose enclosure URL includes the mapped source parameters `aw_s=0` and `aw_e=4`.
    """
    import app.api.torznab as tn
    import app.api.torznab.api as torznab_api
    from app.providers.aniworld.specials import SpecialEpisodeMapping

    monkeypatch.setattr(
        tn, "_slug_from_query", lambda q, site=None: ("aniworld.to", "kaguya")
    )
    monkeypatch.setattr(
        tn, "resolve_series_title", lambda slug, site="aniworld.to": "Kaguya-sama"
    )
    monkeypatch.setattr(
        tn,
        "list_available_languages_cached",
        lambda session, slug, season, episode, site="aniworld.to": ["German Sub"],
    )
    monkeypatch.setattr(
        tn,
        "get_availability",
        lambda session, slug, season, episode, language, site="aniworld.to": None,
    )

    def _probe_quality(slug, season, episode, language, site="aniworld.to", **_kwargs):
        """
        Determine if the specified episode is available as a 1080p H.264 release and provide its metadata.

        Parameters:
                slug (str): Series identifier (ignored by this probe).
                season (int): Season number to probe.
                episode (int): Episode number to probe.
                language (str): Language tag (ignored by this probe).
                site (str): Site identifier (ignored by this probe).

        Returns:
                available (bool): `True` if the probe found a matching 1080p H.264 release, `False` otherwise.
                height (int or None): Video height in pixels when available (1080), otherwise `None`.
                vcodec (str or None): Video codec string when available ("h264"), otherwise `None`.
                release_language (str or None): Release language tag when available ("VOE"), otherwise `None`.
                extra (dict or None): Additional metadata (empty dict when available), otherwise `None`.
        """
        _ = (slug, language, site)
        if season == 0 and episode == 4:
            return (True, 1080, "h264", "VOE", {})
        return (False, None, None, None, None)

    monkeypatch.setattr(tn, "probe_episode_quality", _probe_quality)
    monkeypatch.setattr(tn, "upsert_availability", lambda *args, **kwargs: None)
    monkeypatch.setattr(tn, "build_release_name", _fake_release_name)
    monkeypatch.setattr(tn, "build_magnet", _fake_magnet)
    monkeypatch.setattr(
        torznab_api,
        "resolve_special_mapping_from_episode_request",
        lambda **_kwargs: SpecialEpisodeMapping(
            source_season=0,
            source_episode=4,
            alias_season=0,
            alias_episode=5,
            metadata_title="special title",
            metadata_tvdb_id=12345,
        ),
    )

    resp = client.get(
        "/torznab/api",
        params={"t": "tvsearch", "q": "Kaguya", "season": 0, "ep": 5, "cat": "5070"},
    )
    assert resp.status_code == 200
    root = ET.fromstring(resp.text)
    item = root.find("./channel/item")
    assert item is not None
    title = item.findtext("title") or ""
    assert "S00E05" in title
    enclosure = item.find("enclosure")
    assert enclosure is not None
    url = enclosure.get("url") or ""
    assert "aw_s=0" in url
    assert "aw_e=4" in url
