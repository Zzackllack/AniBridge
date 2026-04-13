from app.hosts import detect_host, resolve_host_url


def test_detect_host_matches_known_embed_domain():
    host = detect_host("https://voe.sx/e/abc123")
    assert host is not None
    assert host.name == "VOE"


def test_resolve_host_url_returns_embed_when_unknown():
    direct_url, host_name = resolve_host_url("https://example.invalid/embed/123")
    assert direct_url is None
    assert host_name == "EMBED"
