import time


def test_catalog_scheduler_runs_immediately(monkeypatch):
    from app.catalog.indexer import ProviderCatalogIndexer

    indexer = ProviderCatalogIndexer()
    calls: list[str] = []

    def fake_run_due_once() -> None:
        calls.append("called")
        indexer._stop_event.set()

    monkeypatch.setattr(indexer, "run_due_once", fake_run_due_once)

    indexer._run_loop()

    assert calls == ["called"]


def test_catalog_discovery_logs_heartbeat(monkeypatch):
    import app.catalog.indexer as indexer_module
    from app.catalog.indexer import ProviderCatalogIndexer

    messages: list[str] = []

    def fake_info(message: str, *args) -> None:
        messages.append(message.format(*args))

    def fake_crawl(_provider: str) -> list[object]:
        time.sleep(0.03)
        return []

    monkeypatch.setattr(indexer_module, "_DISCOVERY_HEARTBEAT_SECONDS", 0.01)
    monkeypatch.setattr(indexer_module, "crawl_provider_catalog", fake_crawl)
    monkeypatch.setattr(indexer_module.logger, "info", fake_info)

    titles = ProviderCatalogIndexer()._crawl_provider_catalog_with_heartbeat(
        "aniworld.to"
    )

    assert titles == []
    assert any("still discovering titles after" in message for message in messages)
