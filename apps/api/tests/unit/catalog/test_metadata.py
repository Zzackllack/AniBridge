from __future__ import annotations


def test_ttl_lru_cache_evicts_oldest_entry():
    from app.catalog.metadata import TtlLruCache

    cache = TtlLruCache[str, int](max_entries=2, ttl_seconds=3600)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert cache.size() == 2


def test_canonical_cache_stats_are_bounded(monkeypatch):
    import app.catalog.metadata as metadata

    search_cache = metadata.TtlLruCache[str, list[dict[str, object]]](
        max_entries=2,
        ttl_seconds=3600,
    )
    show_cache = metadata.TtlLruCache[int, dict[str, object]](
        max_entries=1,
        ttl_seconds=3600,
    )
    monkeypatch.setattr(metadata, "_search_cache", search_cache)
    monkeypatch.setattr(metadata, "_show_cache", show_cache)

    search_cache.set("foo", [{"id": 1}])
    search_cache.set("bar", [{"id": 2}])
    search_cache.set("baz", [{"id": 3}])
    show_cache.set(1, {"id": 1})
    show_cache.set(2, {"id": 2})

    assert metadata.canonical_cache_stats() == {
        "search_entries": 2,
        "show_entries": 1,
    }
