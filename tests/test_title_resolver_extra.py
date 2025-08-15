def test_load_index_from_file(tmp_path, monkeypatch):
    # write minimal HTML
    html = '<a href="/anime/stream/slug-one">Title One</a>'
    p = tmp_path / "alph.html"
    p.write_text(html, encoding="utf-8")

    monkeypatch.setenv("ANIWORLD_ALPHABET_URL", "")
    monkeypatch.setenv("ANIWORLD_ALPHABET_HTML", str(p))
    monkeypatch.setenv("ANIWORLD_TITLES_REFRESH_HOURS", "0")

    import sys
    for m in ["app.config", "app.title_resolver"]:
        if m in sys.modules:
            del sys.modules[m]

    from app.title_resolver import load_or_refresh_index, resolve_series_title

    idx = load_or_refresh_index()
    assert idx == {"slug-one": "Title One"}

    assert resolve_series_title("slug-one") == "Title One"
    assert resolve_series_title(None) is None
