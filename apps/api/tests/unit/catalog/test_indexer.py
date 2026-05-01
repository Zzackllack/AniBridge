from datetime import datetime, timezone
from threading import Event, Thread
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


def test_failed_first_bootstrap_respects_future_retry_backoff():
    from datetime import timedelta

    from app.catalog.indexer import ProviderCatalogIndexer
    from app.db import utcnow

    now = utcnow()
    status = SimpleNamespace(
        provider="aniworld.to",
        status="failed",
        latest_success_generation=None,
        title_index_status="failed",
        title_index_next_retry_after=now + timedelta(hours=2),
        next_refresh_after=None,
    )

    assert ProviderCatalogIndexer()._is_due(status) is False


def test_pick_due_stage_prefers_detail_then_canonical(monkeypatch):
    from app.catalog.indexer import ProviderCatalogIndexer

    indexer = ProviderCatalogIndexer()
    monkeypatch.setattr(indexer, "_detail_stage_has_due_work", lambda provider: True)
    monkeypatch.setattr(indexer, "_canonical_stage_has_due_work", lambda provider: True)

    status = SimpleNamespace(
        provider="aniworld.to",
        status="partial",
        latest_success_generation="gen-1",
        title_index_status="ready",
        detail_enrichment_status="pending",
        detail_next_retry_after=None,
        canonical_enrichment_status="pending",
        canonical_next_retry_after=None,
        next_refresh_after=None,
        title_index_next_retry_after=None,
    )

    assert indexer._pick_due_stage(status) == "detail_enrichment"


def test_pick_due_stage_blocks_title_refresh_while_detail_retry_is_backed_off(
    monkeypatch,
):
    from datetime import timedelta

    from app.catalog.indexer import ProviderCatalogIndexer
    from app.db import utcnow

    indexer = ProviderCatalogIndexer()
    monkeypatch.setattr(indexer, "_detail_stage_has_due_work", lambda provider: True)
    monkeypatch.setattr(
        indexer, "_canonical_stage_has_due_work", lambda provider: False
    )

    status = SimpleNamespace(
        provider="aniworld.to",
        status="partial",
        latest_success_generation="gen-1",
        title_index_status="ready",
        detail_enrichment_status="failed",
        detail_next_retry_after=utcnow() + timedelta(hours=1),
        canonical_enrichment_status="pending",
        canonical_next_retry_after=None,
        next_refresh_after=None,
        title_index_next_retry_after=None,
    )

    assert indexer._pick_due_stage(status) is None


def test_title_index_failure_persists_even_when_writer_shutdown_raises(monkeypatch):
    import app.catalog.indexer as indexer_module
    from app.catalog.indexer import ProviderCatalogIndexer

    indexer = ProviderCatalogIndexer()
    recorded_errors: list[str] = []

    monkeypatch.setattr(
        indexer_module,
        "load_provider_title_index",
        lambda provider, observer=None: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    monkeypatch.setattr(indexer, "_refresh_interval_hours", lambda provider: 24.0)
    monkeypatch.setattr(
        indexer,
        "_signal_title_index_writer_shutdown",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("queue full")),
    )
    monkeypatch.setattr(
        indexer,
        "_ensure_title_index_writer_stopped",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("writer still alive")),
    )
    monkeypatch.setattr(indexer, "_set_progress", lambda *args, **kwargs: None)

    def fake_writer_run(callback):
        session = object()
        return callback(session)

    monkeypatch.setattr(indexer._writer, "run", fake_writer_run)
    monkeypatch.setattr(
        indexer,
        "_finish_title_index_failure",
        lambda session, **kwargs: recorded_errors.append(kwargs["error"]),
    )
    monkeypatch.setattr(
        indexer_module,
        "upsert_provider_index_status",
        lambda session, **kwargs: None,
    )

    indexer._run_title_index_stage("aniworld.to")

    assert recorded_errors
    assert "boom" in recorded_errors[0]
    assert "queue full" in recorded_errors[0]
    assert "writer still alive" in recorded_errors[0]


def test_progress_snapshot_exposes_staged_readiness(client):
    from app.catalog.indexer import get_catalog_indexer
    from app.db import engine, upsert_provider_index_status
    from sqlmodel import Session

    with Session(engine) as session:
        upsert_provider_index_status(
            session,
            provider="aniworld.to",
            refresh_interval_hours=24.0,
            status="partial",
            latest_success_generation="gen-1",
            current_generation="gen-1",
            bootstrap_completed=True,
            title_index_status="ready",
            detail_enrichment_status="pending",
            canonical_enrichment_status="failed",
        )
        upsert_provider_index_status(
            session,
            provider="s.to",
            refresh_interval_hours=24.0,
            status="ready",
            latest_success_generation="gen-1",
            current_generation="gen-1",
            bootstrap_completed=True,
            title_index_status="ready",
            detail_enrichment_status="ready",
            canonical_enrichment_status="ready",
        )
        upsert_provider_index_status(
            session,
            provider="megakino",
            refresh_interval_hours=24.0,
            status="ready",
            latest_success_generation="gen-1",
            current_generation="gen-1",
            bootstrap_completed=True,
            title_index_status="ready",
            detail_enrichment_status="ready",
            canonical_enrichment_status="ready",
        )

    snapshot = get_catalog_indexer().get_progress_snapshot()
    by_provider = {item["provider"]: item for item in snapshot["providers"]}

    assert snapshot["bootstrap_ready"] is True
    assert by_provider["aniworld.to"]["search_ready"] is True
    assert by_provider["aniworld.to"]["full_ready"] is False
    assert by_provider["aniworld.to"]["detail_enrichment_status"] == "pending"
    assert by_provider["aniworld.to"]["canonical_enrichment_status"] == "failed"


def test_ensure_status_rows_backfills_legacy_ready_stage_fields(monkeypatch):
    import app.catalog.indexer as indexer_module
    from app.catalog.indexer import ProviderCatalogIndexer
    from app.db import utcnow

    ready_at = utcnow()
    legacy_status = SimpleNamespace(
        bootstrap_completed=True,
        latest_success_generation="gen-1",
        title_index_status="pending",
        latest_completed_at=ready_at,
        latest_success_at=ready_at,
        status="ready",
    )
    recorded: list[dict[str, object]] = []

    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(indexer_module, "Session", lambda _engine: FakeSession())
    monkeypatch.setattr(
        indexer_module,
        "get_provider_index_status",
        lambda _session, provider: legacy_status,
    )

    indexer = ProviderCatalogIndexer()
    monkeypatch.setattr(
        indexer._writer,
        "run",
        lambda callback: callback(object()),
    )
    monkeypatch.setattr(
        indexer_module,
        "upsert_provider_index_status",
        lambda _session, **kwargs: recorded.append(kwargs),
    )

    indexer._ensure_status_rows()

    assert any(item["title_index_status"] == "ready" for item in recorded)
    assert any(item["detail_enrichment_status"] == "ready" for item in recorded)
    assert any(item["canonical_enrichment_status"] == "ready" for item in recorded)


def test_write_coordinator_serializes_callbacks(monkeypatch):
    import app.catalog.indexer as indexer_module
    from app.catalog.indexer import CatalogIndexWriteCoordinator

    started = Event()
    release = Event()
    order: list[str] = []

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def commit(self):
            return None

    monkeypatch.setattr(indexer_module, "Session", lambda _engine: FakeSession())

    coordinator = CatalogIndexWriteCoordinator()

    def first() -> None:
        coordinator.run(
            lambda _session: (order.append("first"), started.set(), release.wait(1))
        )

    def second() -> None:
        started.wait(1)
        coordinator.run(lambda _session: order.append("second"))

    t1 = Thread(target=first)
    t2 = Thread(target=second)
    t1.start()
    t2.start()
    started.wait(1)
    assert order == ["first"]
    release.set()
    t1.join()
    t2.join()

    assert order == ["first", "second"]


def test_detail_stage_persists_one_title_incrementally(client):
    from app.catalog.indexer import ProviderCatalogIndexer
    from app.catalog.providers import EpisodeLanguageRecord, EpisodeRecord, TitleRecord
    from app.db import (
        ProviderCatalogEpisode,
        ProviderTitleIndexState,
        engine,
        replace_provider_catalog_title,
        upsert_provider_index_status,
        upsert_provider_title_index_state,
    )
    from sqlmodel import Session, select

    with Session(engine) as session:
        upsert_provider_index_status(
            session,
            provider="aniworld.to",
            refresh_interval_hours=24.0,
            status="partial",
            latest_success_generation="gen-1",
            current_generation="gen-1",
            bootstrap_completed=True,
            title_index_status="ready",
            detail_enrichment_status="pending",
            canonical_enrichment_status="pending",
        )
        replace_provider_catalog_title(
            session,
            provider="aniworld.to",
            slug="demo",
            title="Demo",
            media_type_hint="series",
            relative_path="/anime/stream/demo",
            indexed_generation="gen-1",
        )
        upsert_provider_title_index_state(
            session,
            provider="aniworld.to",
            slug="demo",
            detail_status="pending",
        )
        session.commit()

    indexer = ProviderCatalogIndexer()
    indexer._persist_stage_success(
        provider="aniworld.to",
        stage="detail_enrichment",
        title_row=SimpleNamespace(slug="demo"),
        payload=TitleRecord(
            provider="aniworld.to",
            slug="demo",
            title="Demo",
            aliases=["Demo"],
            media_type_hint="series",
            relative_path="/anime/stream/demo",
            episodes=[
                EpisodeRecord(
                    season=1,
                    episode=1,
                    relative_path="/anime/stream/demo/staffel-1/episode-1",
                    title_primary="Episode 1",
                    title_secondary=None,
                    media_type_hint="episode",
                    languages=[
                        EpisodeLanguageRecord(
                            language="German Dub",
                            host_hints=["VOE"],
                        )
                    ],
                )
            ],
        ),
    )

    with Session(engine) as session:
        episodes = session.exec(select(ProviderCatalogEpisode)).all()
        state = session.get(ProviderTitleIndexState, ("aniworld.to", "demo"))

    assert len(episodes) == 1
    assert state is not None
    assert state.detail_status == "ready"


def test_run_row_stage_does_not_mark_ready_when_only_future_retries_remain(
    monkeypatch,
):
    from app.catalog.indexer import ProviderCatalogIndexer

    indexer = ProviderCatalogIndexer()
    events: list[str] = []

    monkeypatch.setattr(indexer, "_refresh_interval_hours", lambda provider: 24.0)
    monkeypatch.setattr(indexer, "_visible_generation", lambda provider: "gen-1")
    monkeypatch.setattr(indexer, "_count_visible_titles", lambda provider: 1)
    monkeypatch.setattr(indexer, "_load_due_stage_rows", lambda **kwargs: [])
    monkeypatch.setattr(
        indexer,
        "_count_remaining_stage_rows",
        lambda session, **kwargs: 1,
    )
    monkeypatch.setattr(indexer, "_set_progress", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        indexer._writer,
        "run",
        lambda callback: callback(object()),
    )
    monkeypatch.setattr(
        indexer,
        "_mark_stage_running",
        lambda **kwargs: events.append("running"),
    )
    monkeypatch.setattr(
        indexer,
        "_mark_stage_pending",
        lambda session, **kwargs: events.append("pending"),
    )
    monkeypatch.setattr(
        indexer,
        "_mark_stage_ready",
        lambda *args, **kwargs: events.append("ready"),
    )

    indexer._run_row_stage(
        provider="aniworld.to",
        stage="detail_enrichment",
        concurrency=1,
    )

    assert events == ["running", "pending"]
