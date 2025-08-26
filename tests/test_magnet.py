def test_build_and_parse_magnet_roundtrip():
    from app.utils.magnet import build_magnet, parse_magnet

    uri = build_magnet(
        title="Title",
        slug="slug",
        season=1,
        episode=2,
        language="German Dub",
        provider="prov",
    )
    parsed = parse_magnet(uri)
    assert parsed["dn"] == "Title"
    assert parsed["aw_slug"] == "slug"
    assert parsed["aw_s"] == "1"
    assert parsed["aw_e"] == "2"
    assert parsed["aw_lang"] == "German Dub"
    assert parsed["xt"].startswith("urn:btih:")
    assert parsed.get("aw_provider") == "prov"


def test_parse_magnet_errors():
    from app.utils.magnet import parse_magnet
    import pytest

    with pytest.raises(ValueError):
        parse_magnet("not-a-magnet")

    # Missing required param
    bad = "magnet:?dn=Title&xt=urn:btih:abc&aw_slug=slug&aw_s=1&aw_e=2"
    with pytest.raises(ValueError):
        parse_magnet(bad)
