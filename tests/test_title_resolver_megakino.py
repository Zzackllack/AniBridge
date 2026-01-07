import sys


class _StubClient:
    """Stub Megakino client that provides a fixed index for resolver tests."""

    def __init__(self, entries):
        """
        Initialize the stub client with a pre-populated index.
        
        Parameters:
            entries (dict): Mapping of slug (str) to entry data used by the client's index methods.
        """
        self._entries = entries

    def load_index(self):
        """
        Return the stored index entries for this stub client.
        
        Returns:
            dict: The entries provided to the client during initialization.
        """
        return self._entries

    def search(self, query, limit=1):
        """
        Perform a search against the client's index using the provided query.
        
        Parameters:
            query (str): The search query string.
            limit (int): Maximum number of results to return.
        
        Returns:
            list: Matching entries from the index; this stub implementation always returns an empty list.
        """
        return []



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
        "get_default_client",
        lambda: _StubClient({"stranger-things-5-stafffel": None}),
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
        "get_default_client",
        lambda: _StubClient({}),
    )

    assert title_resolver.slug_from_query("Stranger Things", site="megakino") is None
