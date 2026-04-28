import time
from types import SimpleNamespace


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


def test_catalog_recovers_interrupted_running_state(monkeypatch):
    import app.catalog.indexer as indexer_module
    from app.catalog.indexer import ProviderCatalogIndexer

    updates: list[dict[str, object]] = []
    warnings: list[str] = []
    statuses = {
        "aniworld.to": SimpleNamespace(
            provider="aniworld.to",
            status="running",
            bootstrap_completed=False,
            latest_started_at=None,
            latest_success_generation=None,
            next_refresh_after=None,
            failure_count=2,
            cursor_title_slug="one-piece",
        ),
        "s.to": None,
        "megakino": SimpleNamespace(
            provider="megakino",
            status="ready",
            bootstrap_completed=True,
            latest_started_at=None,
            latest_success_generation="abc123",
            next_refresh_after=None,
            failure_count=0,
            cursor_title_slug=None,
        ),
    }

    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_warning(message: str, *args) -> None:
        warnings.append(message.format(*args))

    def fake_get_provider_index_status(_session, provider: str):
        return statuses[provider]

    def fake_upsert_provider_index_status(_session, **kwargs):
        updates.append(kwargs)
        return None

    monkeypatch.setattr(indexer_module, "Session", lambda _engine: FakeSession())
    monkeypatch.setattr(
        indexer_module, "get_provider_index_status", fake_get_provider_index_status
    )
    monkeypatch.setattr(
        indexer_module,
        "upsert_provider_index_status",
        fake_upsert_provider_index_status,
    )
    monkeypatch.setattr(indexer_module.logger, "warning", fake_warning)

    ProviderCatalogIndexer()._ensure_status_rows()

    assert any("recovered interrupted run for aniworld.to" in item for item in warnings)
    assert any("Initial bootstrap required" in item for item in warnings)
    assert any(
        update.get("provider") == "aniworld.to" and update.get("status") == "pending"
        for update in updates
    )
    assert any(
        update.get("provider") == "s.to" and update.get("status") == "pending"
        for update in updates
    )


def test_refresh_provider_starts_background_worker(monkeypatch):
    from app.catalog.indexer import ProviderCatalogIndexer

    indexer = ProviderCatalogIndexer()
    called: list[str] = []

    def fake_refresh(provider: str) -> None:
        called.append(provider)

    monkeypatch.setattr(indexer, "_refresh_provider", fake_refresh)

    indexer.refresh_provider("aniworld.to")
    indexer.stop()

    assert called == ["aniworld.to"]
