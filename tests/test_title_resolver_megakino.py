import sys


class _StubProvider:
    """Stub Megakino provider for resolver tests."""

    def __init__(self, slug=None):
        self._slug = slug
        self.alphabet_url = ""
        self.alphabet_html = None

    def load_or_refresh_index(self):
        return {}

    def load_or_refresh_alternatives(self):
        return {}

    def resolve_title(self, slug):
        return None

    def search_slug(self, query):
        if self._slug:
            return type("_Match", (), {"slug": self._slug, "score": 1})()
        return None


def _reload_modules():
    """
    Remove cached imports of app.config and app.utils.title_resolver from sys.modules.

    Deletes the entries for those module names from the import cache so subsequent imports
    will load fresh copies (useful in tests that modify environment or module-level state).
    """
    for m in ["app.config", "app.utils.title_resolver"]:
        if m in sys.modules:
            del sys.modules[m]


def test_slug_from_query_megakino_direct_slug(monkeypatch):
    """Ensure direct megakino slugs resolve without lookup."""
    monkeypatch.setenv("CATALOG_SITES", "megakino")
    monkeypatch.setenv("MEGAKINO_BASE_URL", "https://megakino1.to")
    _reload_modules()

    from app.utils import title_resolver

    monkeypatch.setattr(
        title_resolver,
        "_PROVIDER_CACHE",
        {"megakino": _StubProvider("stranger-things-5-stafffel")},
    )

    assert title_resolver.slug_from_query("stranger-things-5-stafffel") == (
        "megakino",
        "stranger-things-5-stafffel",
    )


def test_slug_from_query_megakino_url(monkeypatch):
    """Ensure megakino URLs resolve to slugs."""
    monkeypatch.setenv("CATALOG_SITES", "megakino")
    monkeypatch.setenv("MEGAKINO_BASE_URL", "https://megakino1.to")
    _reload_modules()

    from app.utils import title_resolver

    monkeypatch.setattr(
        title_resolver,
        "_PROVIDER_CACHE",
        {"megakino": _StubProvider()},
    )

    url = "https://megakino1.to/serials/5877-stranger-things-5-stafffel.html"
    assert title_resolver.slug_from_query(url, site="megakino") == (
        "megakino",
        "stranger-things-5-stafffel",
    )


def test_slug_from_query_megakino_rejects_plain_title(monkeypatch):
    """Ensure plain titles do not resolve when sitemap search is empty."""
    monkeypatch.setenv("CATALOG_SITES", "megakino")
    monkeypatch.setenv("MEGAKINO_BASE_URL", "https://megakino1.to")
    _reload_modules()

    from app.utils import title_resolver

    monkeypatch.setattr(
        title_resolver,
        "_PROVIDER_CACHE",
        {"megakino": _StubProvider()},
    )

    assert title_resolver.slug_from_query("Stranger Things", site="megakino") is None
