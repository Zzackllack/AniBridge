import pytest


def test_caps_xml_parses(stub_aniworld_parser):
    import xml.etree.ElementTree as ET

    del stub_aniworld_parser
    from app.api.torznab import _caps_xml

    xml = _caps_xml()
    root = ET.fromstring(xml)
    assert root.tag == "caps"
    tvsearch = root.find("./searching/tv-search")
    assert tvsearch is not None
    supported = tvsearch.get("supportedParams") or ""
    for expected in ("tvdbid", "tmdbid", "imdbid", "rid", "tvmazeid"):
        assert expected in supported


def test_torznab_apikey_compare_is_unicode_safe_and_constant_time(monkeypatch):
    from fastapi import HTTPException

    from app.api.torznab import utils as torznab_utils

    monkeypatch.setattr(torznab_utils, "INDEXER_API_KEY", "schöne-key")
    torznab_utils._require_apikey("schöne-key")
    for supplied in ("schöne-keyx", "日本語", "", None):
        with pytest.raises(HTTPException) as error:
            torznab_utils._require_apikey(supplied)
        assert error.value.status_code == 401
    calls = []
    monkeypatch.setattr(
        torznab_utils.hmac,
        "compare_digest",
        lambda left, right: calls.append((left, right)) or False,
    )
    with pytest.raises(HTTPException):
        torznab_utils._require_apikey("schöne-key")
    assert calls == [("schöne-key".encode(), "schöne-key".encode())]


def test_slug_from_query_basic(stub_aniworld_parser, monkeypatch):
    del stub_aniworld_parser
    from app.api.torznab import utils as torznab_utils
    from app import utils as app_utils

    # Mock the title_resolver slug_from_query
    def mock_slug_from_query(q, _site=None):
        """
        Provide a test stub that returns a fixed (site_domain, slug) for queries containing "My Title".

        Parameters:
            q (str): Query string to inspect.
            _site (str, optional): Ignored; present to match the real function signature.

        Returns:
            tuple: (`site_domain`, `slug`) when `q` contains "My Title", `None` otherwise.
        """
        if "My Title" in q:
            return ("aniworld.to", "slug")
        return None

    monkeypatch.setattr(
        app_utils.title_resolver, "slug_from_query", mock_slug_from_query
    )
    result = torznab_utils._slug_from_query("My Title")
    assert result == ("aniworld.to", "slug")
    assert torznab_utils._slug_from_query("Unknown") is None
