"""Protect the query-mode qBittorrent routes from registration-order drift."""

# These paths exist in both the legacy shim and the query-mode shim. Starlette
# dispatches the first matching route, so query mode depends on registering the
# query router before the legacy router. Keep the list next to the guard so a
# new overlapping route cannot be added silently.
QUERY_QBITTORRENT_OVERLAP = frozenset(
    {
        ("POST", "/api/v2/torrents/add"),
        ("GET", "/api/v2/torrents/info"),
        ("GET", "/api/v2/sync/maindata"),
        ("GET", "/api/v2/torrents/files"),
        ("GET", "/api/v2/torrents/properties"),
        ("POST", "/api/v2/torrents/delete"),
    }
)

_QUERY_MODULE = "app.catalog.qbit_http"


def assert_query_precedence(routes) -> None:
    """Fail startup when a legacy handler wins an overlapping query path."""
    first_owner: dict[tuple[str, str], str] = {}
    for route in routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or ()
        endpoint = getattr(route, "endpoint", None)
        module = getattr(endpoint, "__module__", "")
        for method in methods:
            key = (method.upper(), path)
            if key in QUERY_QBITTORRENT_OVERLAP and key not in first_owner:
                first_owner[key] = module
    shadowed = sorted(
        key for key, module in first_owner.items() if module != _QUERY_MODULE
    )
    if shadowed:
        detail = ", ".join(f"{method} {path}" for method, path in shadowed)
        raise RuntimeError(
            "query-mode qBittorrent routes must be registered before legacy "
            f"routes; shadowed: {detail}"
        )
