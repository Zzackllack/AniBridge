import sys


class _StubClient:
    def __init__(self, entries):
        self._entries = entries

    def load_index(self):
        return self._entries

    def search(self, query, limit=1):
        return []



def _reload_modules():
    for m in ["app.config", "app.utils.title_resolver"]:
        if m in sys.modules:
            del sys.modules[m]


def test_slug_from_query_megakino_direct_slug(monkeypatch):
    monkeypatch.setenv("CATALOG_SITES", "megakino")
    monkeypatch.setenv("MEGAKINO_BASE_URL", "https://megakino.lol")
    _reload_modules()

    from app.utils import title_resolver

    monkeypatch.setattr(
        title_resolver,
        "get_default_client",
        lambda: _StubClient({"stranger-things-5-stafffel": None}),
    )

    assert title_resolver.slug_from_query("stranger-things-5-stafffel") == (
        "megakino",
        "stranger-things-5-stafffel",
    )


def test_slug_from_query_megakino_url(monkeypatch):
    monkeypatch.setenv("CATALOG_SITES", "megakino")
    monkeypatch.setenv("MEGAKINO_BASE_URL", "https://megakino.lol")
    _reload_modules()

    from app.utils import title_resolver

    url = "https://megakino.lol/serials/5877-stranger-things-5-stafffel.html"
    assert title_resolver.slug_from_query(url, site="megakino") == (
        "megakino",
        "stranger-things-5-stafffel",
    )


def test_slug_from_query_megakino_rejects_plain_title(monkeypatch):
    monkeypatch.setenv("CATALOG_SITES", "megakino")
    monkeypatch.setenv("MEGAKINO_BASE_URL", "https://megakino.lol")
    _reload_modules()

    from app.utils import title_resolver

    monkeypatch.setattr(
        title_resolver,
        "get_default_client",
        lambda: _StubClient({}),
    )

    assert title_resolver.slug_from_query("Stranger Things", site="megakino") is None
