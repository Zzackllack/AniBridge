def _stub_aniworld_parser() -> None:
    """
    Create and inject a minimal stub module named "aniworld.parser" into sys.modules for tests.
    
    The stub provides a `parse_arguments()` callable that returns an empty argparse.Namespace and an `arguments` attribute set to an empty argparse.Namespace, allowing code that imports `aniworld.parser` to operate without the real package.
    """
    import argparse
    import sys
    import types

    stub_parser = types.ModuleType("aniworld.parser")
    stub_parser.parse_arguments = lambda: argparse.Namespace()
    stub_parser.arguments = argparse.Namespace()
    sys.modules["aniworld.parser"] = stub_parser


def test_caps_xml_parses():
    import xml.etree.ElementTree as ET

    _stub_aniworld_parser()
    from app.api.torznab import _caps_xml

    xml = _caps_xml()
    root = ET.fromstring(xml)
    assert root.tag == "caps"
    tvsearch = root.find("./searching/tv-search")
    assert tvsearch is not None
    supported = tvsearch.get("supportedParams") or ""
    for expected in ("tvdbid", "tmdbid", "imdbid", "rid", "tvmazeid"):
        assert expected in supported


def test_slug_from_query_basic(monkeypatch):
    _stub_aniworld_parser()
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