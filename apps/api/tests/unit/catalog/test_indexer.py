from datetime import datetime, timezone
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


def test_catalog_progress_tracks_crawl_and_persist_counts():
    from app.catalog.indexer import ProviderCatalogIndexer

    indexer = ProviderCatalogIndexer()
    indexer._set_progress(
        "aniworld.to",
        phase="crawling_titles",
        total_titles=10,
        reset_log_steps=True,
    )
    indexer._advance_crawl_progress(
        "aniworld.to",
        current_slug="slug-1",
        queue_depth=3,
    )
    indexer._advance_failed_progress(
        "aniworld.to",
        current_slug="slug-2",
        queue_depth=2,
    )
    indexer._advance_persist_progress(
        "aniworld.to",
        current_slug="slug-1",
        count=1,
        queue_depth=1,
    )

    assert indexer._get_total_titles("aniworld.to") == 10
    assert indexer._get_persisted_titles("aniworld.to") == 1
    assert indexer._get_failed_titles("aniworld.to") == 1
    assert indexer._get_writer_lag("aniworld.to") == 0


def test_stale_generation_detection_handles_running_and_published_states():
    from app.catalog.indexer import ProviderCatalogIndexer

    indexer = ProviderCatalogIndexer()

    assert (
        indexer._stale_generation(
            SimpleNamespace(
                status="running",
                current_generation="gen-running",
                latest_success_generation="gen-old",
            )
        )
        == "gen-running"
    )
    assert (
        indexer._stale_generation(
            SimpleNamespace(
                status="failed",
                current_generation="gen-staging",
                latest_success_generation="gen-old",
            )
        )
        == "gen-staging"
    )
    assert (
        indexer._stale_generation(
            SimpleNamespace(
                status="ready",
                current_generation="gen-live",
                latest_success_generation="gen-live",
            )
        )
        is None
    )


def test_catalog_recovers_interrupted_running_state(monkeypatch):
    import app.catalog.indexer as indexer_module
    from app.catalog.indexer import ProviderCatalogIndexer

    updates: list[dict[str, object]] = []
    cleaned: list[tuple[str, str]] = []
    warnings: list[str] = []
    statuses = {
        "aniworld.to": SimpleNamespace(
            provider="aniworld.to",
            status="running",
            bootstrap_completed=False,
            current_generation="staging-123",
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
            current_generation="abc123",
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

    def fake_delete_provider_generation(_session, *, provider: str, generation: str):
        cleaned.append((provider, generation))

    monkeypatch.setattr(indexer_module, "Session", lambda _engine: FakeSession())
    monkeypatch.setattr(
        indexer_module, "get_provider_index_status", fake_get_provider_index_status
    )
    monkeypatch.setattr(
        indexer_module, "delete_provider_generation", fake_delete_provider_generation
    )
    monkeypatch.setattr(
        indexer_module,
        "upsert_provider_index_status",
        fake_upsert_provider_index_status,
    )
    monkeypatch.setattr(indexer_module.logger, "warning", fake_warning)

    ProviderCatalogIndexer()._ensure_status_rows()

    assert any(
        "found interrupted staging generation for aniworld.to" in item
        for item in warnings
    )
    assert any("Initial bootstrap required" in item for item in warnings)
    assert cleaned == [("aniworld.to", "staging-123")]
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


def test_is_due_handles_naive_next_refresh_after():
    from app.catalog.indexer import ProviderCatalogIndexer

    status = SimpleNamespace(
        status="ready",
        latest_success_at=datetime.now(timezone.utc),
        next_refresh_after=datetime(2000, 1, 1, 0, 0, 0),
    )

    assert ProviderCatalogIndexer()._is_due(status) is True
