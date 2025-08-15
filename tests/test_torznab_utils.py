def test_caps_xml_parses():
    import xml.etree.ElementTree as ET
    from app.torznab import _caps_xml

    xml = _caps_xml()
    root = ET.fromstring(xml)
    assert root.tag == "caps"


def test_slug_from_query_basic(monkeypatch):
    from app import torznab as tn

    monkeypatch.setattr(tn, "load_or_refresh_index", lambda: {"slug": "My Title"})
    assert tn._slug_from_query("My Title") == "slug"
    assert tn._slug_from_query("Unknown") is None
