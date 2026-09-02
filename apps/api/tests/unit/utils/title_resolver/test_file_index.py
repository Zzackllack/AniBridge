def test_load_index_from_file(tmp_path, monkeypatch):
    # write minimal HTML
    html = '<a href="/anime/stream/slug-one">Title One</a>'
    p = tmp_path / "alph.html"
    p.write_text(html, encoding="utf-8")

    monkeypatch.setenv("ANIWORLD_ALPHABET_URL", "")
    monkeypatch.setenv("ANIWORLD_ALPHABET_HTML", str(p))
    monkeypatch.setenv("ANIWORLD_TITLES_REFRESH_HOURS", "0")

    import sys

    for m in ["app.config", "app.utils.title_resolver"]:
        if m in sys.modules:
            del sys.modules[m]

    from app.utils.title_resolver import load_or_refresh_index, resolve_series_title

    idx = load_or_refresh_index()
    assert idx == {"slug-one": "Title One"}

    assert resolve_series_title("slug-one") == "Title One"
    assert resolve_series_title(None) is None


def test_resolve_series_title_falls_back_when_index_db_is_unavailable(monkeypatch):
    import app.utils.title_resolver as tr
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(
        tr,
        "Session",
        lambda _engine: (_ for _ in ()).throw(
            OperationalError("stmt", {}, Exception("db down"))
        ),
    )
    monkeypatch.setattr(
        tr,
        "load_or_refresh_index",
        lambda site="aniworld.to": {"slug-one": "Title One"},
    )

    assert tr.resolve_series_title("slug-one") == "Title One"


def test_load_alternatives_falls_back_when_index_db_is_unavailable(monkeypatch):
    import app.utils.title_resolver as tr
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(tr, "get_catalog_readiness_error", lambda: None)
    monkeypatch.setattr(
        tr,
        "Session",
        lambda _engine: (_ for _ in ()).throw(
            OperationalError("stmt", {}, Exception("db down"))
        ),
    )
    monkeypatch.setattr(
        tr, "_cached_alts", {"aniworld.to": {"slug-one": ["Title One"]}}
    )
    monkeypatch.setattr(tr, "_get_site_cfg", lambda site: {})
    monkeypatch.setattr(tr, "_should_refresh", lambda *args, **kwargs: False)

    assert tr.load_or_refresh_alternatives() == {"slug-one": ["Title One"]}
