from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import timedelta
from queue import Empty, Full, Queue
from threading import Event, Lock, Semaphore, Thread
from time import monotonic
from uuid import uuid4

from loguru import logger
from sqlmodel import Session, select

from app.catalog.exceptions import CatalogNotReadyError
from app.catalog.providers import (
    CanonicalPayload,
    CatalogCrawlObserver,
    EpisodeLanguageRecord,
    EpisodeRecord,
    TitleRecord,
    crawl_provider_title_detail,
    load_provider_title_index,
    resolve_provider_canonical,
)
from app.config import (
    ANIBRIDGE_TEST_MODE,
    CANONICAL_INDEX_CONCURRENCY,
    CATALOG_SITES_LIST,
    CATALOG_SITE_CONFIGS,
    PROGRESS_STEP_PERCENT,
    PROVIDER_INDEX_BACKPRESSURE_LOG_SECONDS,
    PROVIDER_INDEX_FAILURE_THRESHOLD_PERCENT,
    PROVIDER_INDEX_GLOBAL_CONCURRENCY,
    PROVIDER_INDEX_QUEUE_SIZE,
    PROVIDER_INDEX_SCHEDULER_POLL_SECONDS,
    PROVIDER_INDEX_TITLE_TIMEOUT_SECONDS,
    PROVIDER_INDEX_WRITER_BATCH_SIZE,
    PROVIDER_INDEX_WRITER_FLUSH_SECONDS,
)
from app.db import (
    ProviderCatalogAlias,
    ProviderCatalogEpisode,
    ProviderCatalogTitle,
    ProviderEpisodeLanguage,
    ProviderIndexStatus,
    ProviderTitleIndexState,
    as_aware_utc,
    delete_provider_generation,
    engine,
    get_provider_index_status,
    is_catalog_bootstrap_ready,
    is_provider_fully_ready,
    list_provider_index_statuses,
    prune_provider_generation,
    replace_canonical_episodes,
    replace_provider_catalog_aliases,
    replace_provider_catalog_episodes,
    replace_provider_catalog_title,
    replace_provider_episode_mappings,
    replace_provider_movie_mappings,
    replace_provider_series_mappings,
    upsert_canonical_series,
    upsert_provider_index_status,
    upsert_provider_title_index_state,
    utcnow,
)
from app.utils.terminal import ProgressReporter, ProgressSnapshot

_INDEXER: "ProviderCatalogIndexer | None" = None
_INDEXER_LOCK = Lock()
_QUEUE_SENTINEL = object()
_UNSET = object()
_STAGES = ("title_index", "detail_enrichment", "canonical_enrichment")


@dataclass(slots=True)
class ProviderCatalogProgress:
    provider: str
    phase: str = "pending"
    stage: str = "title_index"
    crawled_titles: int = 0
    persisted_titles: int = 0
    failed_titles: int = 0
    total_titles: int | None = None
    current_slug: str = ""
    queue_depth: int = 0
    last_logged_crawl_step: int = -1
    last_logged_persist_step: int = -1

    @property
    def processed_titles(self) -> int:
        return self.persisted_titles

    @property
    def writer_lag_titles(self) -> int:
        return max(0, self.crawled_titles - self.persisted_titles)

    @property
    def progress_percent(self) -> float | None:
        if not self.total_titles:
            return None
        if self.total_titles <= 0:
            return 100.0
        return round(
            max(0.0, min(100.0, self.persisted_titles / self.total_titles * 100.0)),
            1,
        )

    @property
    def crawl_percent(self) -> float | None:
        if not self.total_titles:
            return None
        if self.total_titles <= 0:
            return 100.0
        completed = self.crawled_titles + self.failed_titles
        return round(max(0.0, min(100.0, completed / self.total_titles * 100.0)), 1)


class CatalogIndexWriteCoordinator:
    def __init__(self) -> None:
        self._lock = Lock()

    def run(self, callback):
        with self._lock:
            with Session(engine) as session:
                result = callback(session)
                if hasattr(session, "commit"):
                    session.commit()
                return result


def get_catalog_indexer() -> "ProviderCatalogIndexer":
    global _INDEXER
    with _INDEXER_LOCK:
        if _INDEXER is None:
            _INDEXER = ProviderCatalogIndexer()
        return _INDEXER


def get_catalog_readiness_error() -> str | None:
    indexer = get_catalog_indexer()
    with Session(engine) as session:
        statuses = list_provider_index_statuses(session)
        if ANIBRIDGE_TEST_MODE and not statuses:
            return None
        if is_catalog_bootstrap_ready(session, providers=CATALOG_SITES_LIST):
            return None
        pending: list[str] = []
        snapshot = indexer.get_progress_snapshot()
        by_provider = {item["provider"]: item for item in snapshot.get("providers", [])}
        for provider in CATALOG_SITES_LIST:
            status = get_provider_index_status(session, provider=provider)
            search_ready = bool(
                status is not None
                and (status.title_index_status == "ready" or status.bootstrap_completed)
            )
            if status is None or not search_ready:
                progress = by_provider.get(provider, {})
                pending.append(
                    f"{provider} ({progress.get('title_index_status') or 'pending'})"
                )
        if not pending:
            return None
        return (
            "Provider catalog bootstrap is still running. "
            f"Pending providers: {', '.join(pending)}."
        )


def require_catalog_ready() -> None:
    message = get_catalog_readiness_error()
    if message:
        logger.warning("Catalog-dependent request blocked: {}", message)
        raise CatalogNotReadyError(message)


class ProviderCatalogIndexer:
    def __init__(self) -> None:
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._active = Semaphore(PROVIDER_INDEX_GLOBAL_CONCURRENCY)
        self._progress_lock = Lock()
        self._progress: dict[str, ProviderCatalogProgress] = {}
        self._workers_lock = Lock()
        self._workers: dict[str, Thread] = {}
        self._writer = CatalogIndexWriteCoordinator()

    def start(self) -> None:
        self._ensure_status_rows()
        self._log_bootstrap_state()
        if ANIBRIDGE_TEST_MODE:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = Thread(
            target=self._run_loop,
            name="provider-catalog-indexer",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        with self._workers_lock:
            workers = list(self._workers.values())
        for worker in workers:
            worker.join(timeout=5)

    def run_due_once(self) -> None:
        with Session(engine) as session:
            statuses = list_provider_index_statuses(session)
        for status in statuses:
            if self._is_due(status):
                self.refresh_provider(status.provider)

    def refresh_provider(self, provider: str) -> None:
        with self._workers_lock:
            existing = self._workers.get(provider)
            if existing is not None and existing.is_alive():
                return
        if not self._active.acquire(blocking=False):
            return
        worker = Thread(
            target=self._run_provider_refresh,
            name=f"provider-index-{provider}",
            args=(provider,),
            daemon=True,
        )
        with self._workers_lock:
            self._workers[provider] = worker
        worker.start()

    def get_progress_snapshot(self) -> dict[str, object]:
        with Session(engine) as session:
            statuses = {
                status.provider: status
                for status in list_provider_index_statuses(session)
            }
            bootstrap_ready = is_catalog_bootstrap_ready(
                session, providers=CATALOG_SITES_LIST
            )
        with self._progress_lock:
            runtime = {
                provider: ProviderCatalogProgress(
                    provider=snapshot.provider,
                    phase=snapshot.phase,
                    stage=snapshot.stage,
                    crawled_titles=snapshot.crawled_titles,
                    persisted_titles=snapshot.persisted_titles,
                    failed_titles=snapshot.failed_titles,
                    total_titles=snapshot.total_titles,
                    current_slug=snapshot.current_slug,
                    queue_depth=snapshot.queue_depth,
                    last_logged_crawl_step=snapshot.last_logged_crawl_step,
                    last_logged_persist_step=snapshot.last_logged_persist_step,
                )
                for provider, snapshot in self._progress.items()
            }
        providers: list[dict[str, object]] = []
        for provider in CATALOG_SITES_LIST:
            status = statuses.get(provider)
            progress = runtime.get(provider, ProviderCatalogProgress(provider=provider))
            providers.append(
                {
                    "provider": provider,
                    "status": status.status if status is not None else "pending",
                    "active_stage": status.active_stage if status is not None else None,
                    "bootstrap_completed": (
                        bool(status.bootstrap_completed)
                        if status is not None
                        else False
                    ),
                    "title_index_status": (
                        status.title_index_status if status is not None else "pending"
                    ),
                    "detail_enrichment_status": (
                        status.detail_enrichment_status
                        if status is not None
                        else "pending"
                    ),
                    "canonical_enrichment_status": (
                        status.canonical_enrichment_status
                        if status is not None
                        else "pending"
                    ),
                    "search_ready": bool(
                        status is not None
                        and (
                            status.title_index_status == "ready"
                            or status.bootstrap_completed
                        )
                    ),
                    "full_ready": is_provider_fully_ready(status),
                    "phase": progress.phase,
                    "stage": progress.stage,
                    "processed_titles": progress.processed_titles,
                    "crawled_titles": progress.crawled_titles,
                    "persisted_titles": progress.persisted_titles,
                    "failed_titles": progress.failed_titles,
                    "total_titles": progress.total_titles,
                    "progress_percent": progress.progress_percent,
                    "crawl_progress_percent": progress.crawl_percent,
                    "queue_depth": progress.queue_depth,
                    "writer_lag_titles": progress.writer_lag_titles,
                    "current_slug": progress.current_slug or None,
                    "latest_success_generation": (
                        status.latest_success_generation if status is not None else None
                    ),
                    "staging_generation": (
                        status.current_generation
                        if status is not None
                        and status.current_generation
                        != status.latest_success_generation
                        else None
                    ),
                    "last_error_summary": (
                        status.last_error_summary if status is not None else ""
                    ),
                    "latest_started_at": (
                        status.latest_started_at.isoformat()
                        if status is not None and status.latest_started_at is not None
                        else None
                    ),
                    "latest_completed_at": (
                        status.latest_completed_at.isoformat()
                        if status is not None and status.latest_completed_at is not None
                        else None
                    ),
                    "title_index_ready_at": (
                        status.title_index_ready_at.isoformat()
                        if status is not None
                        and status.title_index_ready_at is not None
                        else None
                    ),
                    "detail_ready_at": (
                        status.detail_ready_at.isoformat()
                        if status is not None and status.detail_ready_at is not None
                        else None
                    ),
                    "canonical_ready_at": (
                        status.canonical_ready_at.isoformat()
                        if status is not None and status.canonical_ready_at is not None
                        else None
                    ),
                }
            )
        return {
            "bootstrap_ready": bootstrap_ready,
            "bootstrapping": not bootstrap_ready,
            "full_ready": all(
                is_provider_fully_ready(statuses.get(provider))
                for provider in CATALOG_SITES_LIST
            ),
            "providers": providers,
        }

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_due_once()
            except Exception as exc:
                logger.exception("Provider catalog scheduler loop failed: {}", exc)
            if self._stop_event.wait(PROVIDER_INDEX_SCHEDULER_POLL_SECONDS):
                break

    def _run_provider_refresh(self, provider: str) -> None:
        try:
            self._refresh_provider(provider)
        finally:
            self._active.release()
            with self._workers_lock:
                self._workers.pop(provider, None)

    def _ensure_status_rows(self) -> None:
        for provider in CATALOG_SITES_LIST:
            self._set_progress(provider, phase="pending", stage="title_index")
            hours = self._refresh_interval_hours(provider)
            with Session(engine) as session:
                status = get_provider_index_status(session, provider=provider)
            if status is None:
                logger.warning(
                    "Provider catalog bootstrap: no persisted index state for {}. Initial bootstrap required.",
                    provider,
                )
                self._writer.run(
                    lambda session, provider=provider, hours=hours: (
                        upsert_provider_index_status(
                            session,
                            provider=provider,
                            refresh_interval_hours=hours,
                            status="pending",
                            title_index_status="pending",
                            detail_enrichment_status="pending",
                            canonical_enrichment_status="pending",
                            bootstrap_completed=False,
                            commit=False,
                        )
                    )
                )
                continue
            stale_generation = self._stale_generation(status)
            if stale_generation is not None:
                logger.warning(
                    "Provider catalog bootstrap: found interrupted staging generation for {} generation={} status={} cursor_slug={}. Cleaning it up before retry.",
                    provider,
                    stale_generation,
                    status.status,
                    getattr(status, "cursor_title_slug", None) or None,
                )
                self._writer.run(
                    lambda session, provider=provider, generation=stale_generation, hours=hours: (
                        self._cleanup_stale_generation(
                            session,
                            provider=provider,
                            generation=generation,
                            refresh_interval_hours=hours,
                        )
                    )
                )
                continue
            if self._needs_stage_backfill(status):
                self._writer.run(
                    lambda session, provider=provider, status=status, hours=hours: (
                        self._backfill_legacy_stage_state(
                            session,
                            provider=provider,
                            status=status,
                            refresh_interval_hours=hours,
                        )
                    )
                )

    def _needs_stage_backfill(self, status: ProviderIndexStatus) -> bool:
        return bool(
            getattr(status, "bootstrap_completed", False)
            and getattr(status, "latest_success_generation", None)
            and getattr(status, "title_index_status", "pending") == "pending"
        )

    def _backfill_legacy_stage_state(
        self,
        session: Session,
        *,
        provider: str,
        status: ProviderIndexStatus,
        refresh_interval_hours: float,
    ) -> None:
        ready_at = (
            getattr(status, "latest_completed_at", None)
            or getattr(status, "latest_success_at", None)
            or utcnow()
        )
        full_ready = getattr(status, "status", None) == "ready"
        upsert_provider_index_status(
            session,
            provider=provider,
            refresh_interval_hours=refresh_interval_hours,
            title_index_status="ready",
            title_index_ready_at=getattr(status, "title_index_ready_at", None)
            or ready_at,
            title_index_next_retry_after=None,
            detail_enrichment_status="ready" if full_ready else "pending",
            detail_ready_at=getattr(status, "detail_ready_at", None)
            or (ready_at if full_ready else None),
            detail_next_retry_after=None,
            canonical_enrichment_status="ready" if full_ready else "pending",
            canonical_ready_at=getattr(status, "canonical_ready_at", None)
            or (ready_at if full_ready else None),
            canonical_next_retry_after=None,
            commit=False,
        )

    def _cleanup_stale_generation(
        self,
        session: Session,
        *,
        provider: str,
        generation: str,
        refresh_interval_hours: float,
    ) -> None:
        delete_provider_generation(session, provider=provider, generation=generation)
        current = get_provider_index_status(session, provider=provider)
        upsert_provider_index_status(
            session,
            provider=provider,
            refresh_interval_hours=refresh_interval_hours,
            status="pending",
            active_stage=None,
            current_generation=None,
            latest_completed_at=utcnow(),
            title_index_status="pending",
            detail_enrichment_status="pending",
            canonical_enrichment_status="pending",
            failure_count=0 if current is None else current.failure_count + 1,
            last_error_summary="Interrupted staging generation cleaned up after restart.",
            commit=False,
        )

    def _is_due(self, status: ProviderIndexStatus) -> bool:
        return self._pick_due_stage(status) is not None

    def _stage_due(
        self,
        *,
        stage_status: str,
        retry_after,
        refresh_after=_UNSET,
    ) -> bool:
        if stage_status == "running":
            return False
        now = utcnow()
        if retry_after is not None and as_aware_utc(retry_after) > now:
            return False
        if refresh_after is not _UNSET and refresh_after is not None:
            if as_aware_utc(refresh_after) > now:
                return False
        if stage_status in {"pending", "failed"}:
            return True
        if refresh_after is _UNSET:
            return False
        if refresh_after is None:
            return True
        return as_aware_utc(refresh_after) <= now

    def _pick_due_stage(self, status: ProviderIndexStatus) -> str | None:
        if getattr(status, "status", None) == "running":
            return None
        latest_success_generation = getattr(status, "latest_success_generation", None)
        title_index_status = getattr(status, "title_index_status", None)
        if title_index_status is None:
            title_index_status = "ready" if latest_success_generation else "pending"
        if not latest_success_generation or title_index_status != "ready":
            if self._stage_due(
                stage_status=title_index_status,
                retry_after=getattr(status, "title_index_next_retry_after", None),
                refresh_after=getattr(status, "next_refresh_after", None),
            ):
                return "title_index"
            return None
        if self._detail_stage_has_due_work(status.provider):
            if self._stage_due(
                stage_status=getattr(status, "detail_enrichment_status", "pending"),
                retry_after=getattr(status, "detail_next_retry_after", None),
            ):
                return "detail_enrichment"
        if self._canonical_stage_has_due_work(status.provider):
            if self._stage_due(
                stage_status=getattr(status, "canonical_enrichment_status", "pending"),
                retry_after=getattr(status, "canonical_next_retry_after", None),
            ):
                return "canonical_enrichment"
        if self._stage_due(
            stage_status=title_index_status,
            retry_after=getattr(status, "title_index_next_retry_after", None),
            refresh_after=getattr(status, "next_refresh_after", None),
        ):
            return "title_index"
        return None

    def _refresh_provider(self, provider: str) -> None:
        with Session(engine) as session:
            status = get_provider_index_status(session, provider=provider)
        if status is None:
            return
        stage = self._pick_due_stage(status)
        if stage is None:
            return
        if stage == "title_index":
            self._run_title_index_stage(provider)
            return
        if stage == "detail_enrichment":
            self._run_detail_enrichment_stage(provider)
            return
        if stage == "canonical_enrichment":
            self._run_canonical_enrichment_stage(provider)

    def _run_title_index_stage(self, provider: str) -> None:
        refresh_interval_hours = self._refresh_interval_hours(provider)
        generation = uuid4().hex
        queue: Queue[TitleRecord | object] = Queue(maxsize=PROVIDER_INDEX_QUEUE_SIZE)
        writer_failure: list[BaseException] = []
        self._set_progress(
            provider,
            phase="title_index",
            stage="title_index",
            crawled_titles=0,
            persisted_titles=0,
            failed_titles=0,
            total_titles=None,
            current_slug="",
            queue_depth=0,
            reset_log_steps=True,
        )
        self._writer.run(
            lambda session: upsert_provider_index_status(
                session,
                provider=provider,
                refresh_interval_hours=refresh_interval_hours,
                status="running",
                active_stage="title_index",
                current_generation=generation,
                latest_started_at=utcnow(),
                latest_completed_at=None,
                title_index_status="running",
                title_index_next_retry_after=None,
                last_error_summary="",
                cursor_title_slug="",
                commit=False,
            )
        )

        reporter = ProgressReporter(
            label=f"Catalog {provider}",
            unit="title",
            unit_scale=False,
        )
        writer = Thread(
            target=self._title_index_writer_loop,
            name=f"provider-index-writer-{provider}",
            args=(
                provider,
                generation,
                refresh_interval_hours,
                queue,
                reporter,
                writer_failure,
            ),
            daemon=True,
        )
        writer.start()

        def on_index_loaded(total_titles: int) -> None:
            self._set_progress(
                provider,
                phase="title_index",
                stage="title_index",
                total_titles=total_titles,
                reset_log_steps=True,
            )
            reporter.update(
                ProgressSnapshot(downloaded=0, total=total_titles, status="title_index")
            )

        observer = CatalogCrawlObserver(on_index_loaded=on_index_loaded)
        writer_shutdown_signaled = False

        try:
            rows = load_provider_title_index(provider, observer=observer)
            if self._get_total_titles(provider) is None:
                on_index_loaded(len(rows))
            for row in rows:
                self._enqueue_title_record(provider, queue, row, writer_failure)
                self._advance_crawl_progress(
                    provider,
                    current_slug=row.slug,
                    queue_depth=queue.qsize(),
                )
            self._signal_title_index_writer_shutdown(provider=provider, queue=queue)
            writer_shutdown_signaled = True
            writer.join(timeout=30)
            self._ensure_title_index_writer_stopped(
                provider=provider,
                writer=writer,
                writer_failure=writer_failure,
                timeout_seconds=30,
            )
            if writer_failure:
                raise RuntimeError(str(writer_failure[0]))
            completed_at = utcnow()
            self._writer.run(
                lambda session: self._finish_title_index_success(
                    session,
                    provider=provider,
                    generation=generation,
                    refresh_interval_hours=refresh_interval_hours,
                    completed_at=completed_at,
                )
            )
            self._set_progress(
                provider,
                phase="title_index_ready",
                stage="title_index",
                queue_depth=0,
                current_slug="",
            )
        except Exception as exc:
            logger.exception(
                "Provider catalog title index failed for {}: {}", provider, exc
            )
            if not writer_shutdown_signaled:
                self._signal_title_index_writer_shutdown(provider=provider, queue=queue)
            writer.join(timeout=5)
            self._ensure_title_index_writer_stopped(
                provider=provider,
                writer=writer,
                writer_failure=writer_failure,
                timeout_seconds=5,
            )
            completed_at = utcnow()
            error_text = str(exc)
            self._writer.run(
                lambda session, error=error_text: self._finish_title_index_failure(
                    session,
                    provider=provider,
                    generation=generation,
                    refresh_interval_hours=refresh_interval_hours,
                    completed_at=completed_at,
                    error=error,
                )
            )
            self._set_progress(
                provider,
                phase="failed",
                stage="title_index",
                queue_depth=0,
                current_slug="",
            )
        finally:
            reporter.close()

    def _signal_title_index_writer_shutdown(
        self,
        *,
        provider: str,
        queue: Queue[TitleRecord | object],
    ) -> None:
        try:
            queue.put_nowait(_QUEUE_SENTINEL)
        except Full as exc:
            logger.error(
                "Provider catalog title index writer queue is full during shutdown for {}",
                provider,
            )
            raise RuntimeError(
                f"writer shutdown queue is full for provider {provider}"
            ) from exc

    def _ensure_title_index_writer_stopped(
        self,
        *,
        provider: str,
        writer: Thread,
        writer_failure: list[BaseException],
        timeout_seconds: int,
    ) -> None:
        if writer.is_alive():
            detail = f": {writer_failure[0]}" if writer_failure else ""
            raise RuntimeError(
                f"writer thread did not finish within {timeout_seconds}s for {provider}{detail}"
            )

    def _finish_title_index_success(
        self,
        session: Session,
        *,
        provider: str,
        generation: str,
        refresh_interval_hours: float,
        completed_at,
    ) -> None:
        prune_provider_generation(
            session, provider=provider, keep_generation=generation
        )
        upsert_provider_index_status(
            session,
            provider=provider,
            refresh_interval_hours=refresh_interval_hours,
            status="partial",
            active_stage=None,
            current_generation=generation,
            latest_success_generation=generation,
            latest_completed_at=completed_at,
            latest_success_at=completed_at,
            next_refresh_after=completed_at + timedelta(hours=refresh_interval_hours),
            bootstrap_completed=True,
            title_index_status="ready",
            title_index_ready_at=completed_at,
            title_index_next_retry_after=None,
            detail_enrichment_status="pending",
            detail_ready_at=None,
            detail_next_retry_after=None,
            canonical_enrichment_status="pending",
            canonical_ready_at=None,
            canonical_next_retry_after=None,
            failure_count=0,
            last_error_summary="",
            cursor_title_slug="",
            commit=False,
        )

    def _finish_title_index_failure(
        self,
        session: Session,
        *,
        provider: str,
        generation: str,
        refresh_interval_hours: float,
        completed_at,
        error: str,
    ) -> None:
        delete_provider_generation(session, provider=provider, generation=generation)
        current = get_provider_index_status(session, provider=provider)
        upsert_provider_index_status(
            session,
            provider=provider,
            refresh_interval_hours=refresh_interval_hours,
            status="failed",
            active_stage=None,
            current_generation=None,
            latest_completed_at=completed_at,
            title_index_status="failed",
            title_index_next_retry_after=completed_at
            + timedelta(hours=refresh_interval_hours),
            failure_count=1 if current is None else current.failure_count + 1,
            last_error_summary=error[:500],
            commit=False,
        )

    def _title_index_writer_loop(
        self,
        provider: str,
        generation: str,
        refresh_interval_hours: float,
        queue: Queue[TitleRecord | object],
        reporter: ProgressReporter,
        writer_failure: list[BaseException],
    ) -> None:
        batch: list[TitleRecord] = []
        last_flush_at = monotonic()
        try:
            while True:
                timeout = max(
                    0.1,
                    PROVIDER_INDEX_WRITER_FLUSH_SECONDS - (monotonic() - last_flush_at),
                )
                try:
                    item = queue.get(timeout=timeout)
                except Empty:
                    item = None
                if item is None:
                    if batch:
                        self._flush_title_index_batch(
                            provider=provider,
                            generation=generation,
                            refresh_interval_hours=refresh_interval_hours,
                            batch=batch,
                            queue_depth=queue.qsize(),
                            reporter=reporter,
                        )
                        batch = []
                        last_flush_at = monotonic()
                    continue
                if item is _QUEUE_SENTINEL:
                    if batch:
                        self._flush_title_index_batch(
                            provider=provider,
                            generation=generation,
                            refresh_interval_hours=refresh_interval_hours,
                            batch=batch,
                            queue_depth=queue.qsize(),
                            reporter=reporter,
                        )
                    return
                batch.append(item)
                if len(batch) >= PROVIDER_INDEX_WRITER_BATCH_SIZE:
                    self._flush_title_index_batch(
                        provider=provider,
                        generation=generation,
                        refresh_interval_hours=refresh_interval_hours,
                        batch=batch,
                        queue_depth=queue.qsize(),
                        reporter=reporter,
                    )
                    batch = []
                    last_flush_at = monotonic()
        except BaseException as exc:
            writer_failure.append(exc)

    def _flush_title_index_batch(
        self,
        *,
        provider: str,
        generation: str,
        refresh_interval_hours: float,
        batch: list[TitleRecord],
        queue_depth: int,
        reporter: ProgressReporter,
    ) -> None:
        if not batch:
            return
        last_slug = batch[-1].slug

        def _persist(session: Session) -> None:
            for record in batch:
                now = utcnow()
                upsert_provider_title_index_state(
                    session,
                    provider=provider,
                    slug=record.slug,
                    attempted_at=now,
                    succeeded_at=now,
                    failure_count=0,
                    last_error_summary="",
                    detail_status="pending",
                    detail_next_retry_after=None,
                    detail_failure_count=0,
                    detail_last_error_summary=None,
                    canonical_status="pending",
                    canonical_next_retry_after=None,
                    canonical_failure_count=0,
                    canonical_last_error_summary=None,
                    commit=False,
                )
                replace_provider_catalog_title(
                    session,
                    provider=record.provider,
                    slug=record.slug,
                    title=record.title,
                    media_type_hint=record.media_type_hint,
                    relative_path=record.relative_path,
                    indexed_generation=generation,
                )
                replace_provider_catalog_aliases(
                    session,
                    provider=record.provider,
                    slug=record.slug,
                    aliases=record.aliases,
                    indexed_generation=generation,
                )
            upsert_provider_index_status(
                session,
                provider=provider,
                refresh_interval_hours=refresh_interval_hours,
                status="running",
                active_stage="title_index",
                current_generation=generation,
                cursor_title_slug=last_slug,
                last_error_summary="",
                commit=False,
            )

        self._writer.run(_persist)
        self._advance_persist_progress(
            provider,
            current_slug=last_slug,
            count=len(batch),
            queue_depth=queue_depth,
        )
        reporter.update(
            ProgressSnapshot(
                downloaded=self._get_persisted_titles(provider),
                total=self._get_total_titles(provider),
                status="title_index",
            )
        )

    def _run_detail_enrichment_stage(self, provider: str) -> None:
        self._run_row_stage(
            provider=provider,
            stage="detail_enrichment",
            concurrency=self._provider_concurrency(provider),
        )

    def _run_canonical_enrichment_stage(self, provider: str) -> None:
        self._run_row_stage(
            provider=provider,
            stage="canonical_enrichment",
            concurrency=CANONICAL_INDEX_CONCURRENCY,
        )

    def _run_row_stage(self, *, provider: str, stage: str, concurrency: int) -> None:
        refresh_interval_hours = self._refresh_interval_hours(provider)
        generation = self._visible_generation(provider)
        if generation is None:
            return
        self._mark_stage_running(
            provider=provider,
            stage=stage,
            refresh_interval_hours=refresh_interval_hours,
        )
        total_titles = self._count_visible_titles(provider)
        self._set_progress(
            provider,
            phase=stage,
            stage=stage,
            crawled_titles=0,
            persisted_titles=0,
            failed_titles=0,
            total_titles=total_titles,
            current_slug="",
            queue_depth=0,
            reset_log_steps=True,
        )
        failure_limit = max(
            1,
            int(
                max(1, total_titles) * PROVIDER_INDEX_FAILURE_THRESHOLD_PERCENT / 100.0
            ),
        )
        failure_count = 0
        while not self._stop_event.is_set():
            due_rows = self._load_due_stage_rows(
                provider=provider,
                stage=stage,
                limit=max(1, concurrency * 2),
            )
            if not due_rows:
                remaining_rows = self._writer.run(
                    lambda session: self._count_remaining_stage_rows(
                        session,
                        provider=provider,
                        stage=stage,
                        generation=generation,
                    )
                )
                if remaining_rows:
                    self._writer.run(
                        lambda session: self._mark_stage_pending(
                            session,
                            provider=provider,
                            stage=stage,
                            refresh_interval_hours=refresh_interval_hours,
                        )
                    )
                    return
                completed_at = utcnow()
                self._writer.run(
                    lambda session: self._mark_stage_ready(
                        session,
                        provider=provider,
                        stage=stage,
                        refresh_interval_hours=refresh_interval_hours,
                        completed_at=completed_at,
                    )
                )
                self._set_progress(
                    provider,
                    phase=f"{stage}_ready",
                    stage=stage,
                    current_slug="",
                )
                return
            executor = ThreadPoolExecutor(max_workers=max(1, concurrency))
            pending: dict[
                Future, tuple[ProviderCatalogTitle, ProviderTitleIndexState]
            ] = {}
            try:
                for title_row, state in due_rows:
                    pending[
                        executor.submit(
                            self._run_stage_job,
                            provider=provider,
                            stage=stage,
                            title_row=title_row,
                        )
                    ] = (title_row, state)
                while pending:
                    done, not_done = wait(
                        pending.keys(),
                        timeout=1.0,
                        return_when=FIRST_COMPLETED,
                    )
                    if not done:
                        continue
                    for future in done:
                        title_row, state = pending.pop(future)
                        try:
                            payload = future.result()
                            self._persist_stage_success(
                                provider=provider,
                                stage=stage,
                                title_row=title_row,
                                payload=payload,
                            )
                            self._advance_persist_progress(
                                provider,
                                current_slug=title_row.slug,
                                count=1,
                                queue_depth=len(not_done),
                            )
                        except Exception as exc:
                            failure_count += 1
                            error_text = str(exc)
                            self._persist_stage_failure(
                                provider=provider,
                                stage=stage,
                                title_row=title_row,
                                state=state,
                                error=error_text,
                            )
                            self._advance_failed_progress(
                                provider,
                                current_slug=title_row.slug,
                                queue_depth=len(not_done),
                            )
                            if failure_count >= failure_limit:
                                for remaining in not_done:
                                    remaining.cancel()
                                completed_at = utcnow()
                                self._writer.run(
                                    lambda session, error=error_text: (
                                        self._mark_stage_failed(
                                            session,
                                            provider=provider,
                                            stage=stage,
                                            refresh_interval_hours=refresh_interval_hours,
                                            completed_at=completed_at,
                                            error=error,
                                        )
                                    )
                                )
                                return
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

    def _run_stage_job(
        self,
        *,
        provider: str,
        stage: str,
        title_row: ProviderCatalogTitle,
    ):
        self._advance_crawl_progress(
            provider,
            current_slug=title_row.slug,
            queue_depth=0,
        )
        aliases = self._load_aliases(provider=provider, slug=title_row.slug)
        if stage == "detail_enrichment":
            return crawl_provider_title_detail(
                provider_key=provider,
                slug=title_row.slug,
                title=title_row.title,
                aliases=aliases,
                timeout_seconds=float(
                    CATALOG_SITE_CONFIGS[provider].get(
                        "provider_index_title_timeout_seconds",
                        PROVIDER_INDEX_TITLE_TIMEOUT_SECONDS,
                    )
                ),
            )
        episodes = self._load_episode_records(provider=provider, slug=title_row.slug)
        return resolve_provider_canonical(
            provider_key=provider,
            slug=title_row.slug,
            title=title_row.title,
            aliases=aliases,
            media_type_hint=title_row.media_type_hint,
            episodes=episodes,
        )

    def _persist_stage_success(
        self,
        *,
        provider: str,
        stage: str,
        title_row: ProviderCatalogTitle,
        payload,
    ) -> None:
        generation = self._visible_generation(provider)
        now = utcnow()

        def _persist(session: Session) -> None:
            if stage == "detail_enrichment":
                detail_record: TitleRecord = payload
                replace_provider_catalog_title(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    title=detail_record.title,
                    media_type_hint=detail_record.media_type_hint,
                    relative_path=detail_record.relative_path,
                    indexed_generation=generation,
                )
                replace_provider_catalog_episodes(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    episodes=[
                        {
                            "season": episode.season,
                            "episode": episode.episode,
                            "relative_path": episode.relative_path,
                            "title_primary": episode.title_primary,
                            "title_secondary": episode.title_secondary,
                            "media_type_hint": episode.media_type_hint,
                            "languages": [
                                {
                                    "language": language.language,
                                    "host_hints": language.host_hints,
                                }
                                for language in episode.languages
                            ],
                        }
                        for episode in detail_record.episodes
                    ],
                    indexed_generation=generation,
                )
                upsert_provider_title_index_state(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    detail_status="ready",
                    detail_attempted_at=now,
                    detail_succeeded_at=now,
                    detail_next_retry_after=None,
                    detail_failure_count=0,
                    detail_last_error_summary=None,
                    commit=False,
                )
            else:
                canonical: CanonicalPayload = payload
                if canonical.series is not None:
                    series = canonical.series
                    upsert_canonical_series(
                        session,
                        tvdb_id=int(series["tvdb_id"]),
                        title=str(series["title"]),
                        tmdb_id=series.get("tmdb_id"),
                        imdb_id=series.get("imdb_id"),
                        tvmaze_id=series.get("tvmaze_id"),
                        anilist_id=series.get("anilist_id"),
                        mal_id=series.get("mal_id"),
                        aliases=list(series.get("aliases") or []),
                    )
                    replace_canonical_episodes(
                        session,
                        tvdb_id=int(series["tvdb_id"]),
                        episodes=canonical.episodes,
                    )
                replace_provider_series_mappings(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    mappings=canonical.series_mappings,
                    indexed_generation=generation,
                )
                replace_provider_episode_mappings(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    mappings=canonical.episode_mappings,
                    indexed_generation=generation,
                )
                replace_provider_movie_mappings(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    mappings=canonical.movie_mappings,
                    indexed_generation=generation,
                )
                upsert_provider_title_index_state(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    canonical_status="ready",
                    canonical_attempted_at=now,
                    canonical_succeeded_at=now,
                    canonical_next_retry_after=None,
                    canonical_failure_count=0,
                    canonical_last_error_summary=None,
                    commit=False,
                )

        self._writer.run(_persist)

    def _persist_stage_failure(
        self,
        *,
        provider: str,
        stage: str,
        title_row: ProviderCatalogTitle,
        state: ProviderTitleIndexState,
        error: str,
    ) -> None:
        refresh_interval_hours = self._refresh_interval_hours(provider)
        retry_at = utcnow() + timedelta(hours=refresh_interval_hours)

        def _persist(session: Session) -> None:
            if stage == "detail_enrichment":
                upsert_provider_title_index_state(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    detail_status="failed",
                    detail_attempted_at=utcnow(),
                    detail_next_retry_after=retry_at,
                    detail_failure_count=state.detail_failure_count + 1,
                    detail_last_error_summary=error[:500],
                    commit=False,
                )
            else:
                upsert_provider_title_index_state(
                    session,
                    provider=provider,
                    slug=title_row.slug,
                    canonical_status="failed",
                    canonical_attempted_at=utcnow(),
                    canonical_next_retry_after=retry_at,
                    canonical_failure_count=state.canonical_failure_count + 1,
                    canonical_last_error_summary=error[:500],
                    commit=False,
                )

        self._writer.run(_persist)

    def _mark_stage_running(
        self,
        *,
        provider: str,
        stage: str,
        refresh_interval_hours: float,
    ) -> None:
        def _persist(session: Session) -> None:
            payload = {
                "provider": provider,
                "refresh_interval_hours": refresh_interval_hours,
                "status": "running",
                "active_stage": stage,
                "latest_started_at": utcnow(),
                "last_error_summary": "",
                "commit": False,
            }
            if stage == "detail_enrichment":
                payload["detail_enrichment_status"] = "running"
                payload["detail_next_retry_after"] = None
            elif stage == "canonical_enrichment":
                payload["canonical_enrichment_status"] = "running"
                payload["canonical_next_retry_after"] = None
            upsert_provider_index_status(session, **payload)

        self._writer.run(_persist)

    def _mark_stage_ready(
        self,
        session: Session,
        *,
        provider: str,
        stage: str,
        refresh_interval_hours: float,
        completed_at,
    ) -> None:
        with Session(engine) as read_session:
            status = get_provider_index_status(read_session, provider=provider)
        if status is not None:
            status = status.model_copy(deep=True)
        payload = {
            "provider": provider,
            "refresh_interval_hours": refresh_interval_hours,
            "status": "partial",
            "active_stage": None,
            "latest_completed_at": completed_at,
            "last_error_summary": "",
            "commit": False,
        }
        if stage == "detail_enrichment":
            payload["detail_enrichment_status"] = "ready"
            payload["detail_ready_at"] = completed_at
            payload["detail_next_retry_after"] = None
            if status is not None:
                status.detail_enrichment_status = "ready"
                status.detail_ready_at = completed_at
                status.detail_next_retry_after = None
        else:
            payload["canonical_enrichment_status"] = "ready"
            payload["canonical_ready_at"] = completed_at
            payload["canonical_next_retry_after"] = None
            if status is not None:
                status.canonical_enrichment_status = "ready"
                status.canonical_ready_at = completed_at
                status.canonical_next_retry_after = None
        if status is not None and is_provider_fully_ready(status):
            payload["status"] = "ready"
        upsert_provider_index_status(session, **payload)

    def _mark_stage_pending(
        self,
        session: Session,
        *,
        provider: str,
        stage: str,
        refresh_interval_hours: float,
    ) -> None:
        payload = {
            "provider": provider,
            "refresh_interval_hours": refresh_interval_hours,
            "status": "partial",
            "active_stage": None,
            "last_error_summary": "",
            "commit": False,
        }
        if stage == "detail_enrichment":
            payload["detail_enrichment_status"] = "pending"
        else:
            payload["canonical_enrichment_status"] = "pending"
        upsert_provider_index_status(session, **payload)

    def _mark_stage_failed(
        self,
        session: Session,
        *,
        provider: str,
        stage: str,
        refresh_interval_hours: float,
        completed_at,
        error: str,
    ) -> None:
        payload = {
            "provider": provider,
            "refresh_interval_hours": refresh_interval_hours,
            "status": "failed",
            "active_stage": None,
            "latest_completed_at": completed_at,
            "last_error_summary": error[:500],
            "commit": False,
        }
        retry_at = completed_at + timedelta(hours=refresh_interval_hours)
        if stage == "detail_enrichment":
            payload["detail_enrichment_status"] = "failed"
            payload["detail_next_retry_after"] = retry_at
        else:
            payload["canonical_enrichment_status"] = "failed"
            payload["canonical_next_retry_after"] = retry_at
        upsert_provider_index_status(session, **payload)

    def _detail_stage_has_due_work(self, provider: str) -> bool:
        return bool(
            self._load_due_stage_rows(
                provider=provider, stage="detail_enrichment", limit=1
            )
        )

    def _canonical_stage_has_due_work(self, provider: str) -> bool:
        return bool(
            self._load_due_stage_rows(
                provider=provider, stage="canonical_enrichment", limit=1
            )
        )

    def _load_due_stage_rows(
        self,
        *,
        provider: str,
        stage: str,
        limit: int,
    ) -> list[tuple[ProviderCatalogTitle, ProviderTitleIndexState]]:
        generation = self._visible_generation(provider)
        if generation is None:
            return []
        now = utcnow()
        with Session(engine) as session:
            rows = list(
                session.exec(
                    select(ProviderCatalogTitle).where(
                        (ProviderCatalogTitle.provider == provider)
                        & (ProviderCatalogTitle.indexed_generation == generation)
                    )
                ).all()
            )
            due: list[tuple[ProviderCatalogTitle, ProviderTitleIndexState]] = []
            for row in rows:
                state = session.get(ProviderTitleIndexState, (provider, row.slug))
                if state is None:
                    state = ProviderTitleIndexState(provider=provider, slug=row.slug)
                if stage == "detail_enrichment":
                    retry_after = state.detail_next_retry_after
                    if retry_after is not None and as_aware_utc(retry_after) > now:
                        continue
                    if state.detail_status == "ready":
                        continue
                    due.append((row, state))
                else:
                    retry_after = state.canonical_next_retry_after
                    if retry_after is not None and as_aware_utc(retry_after) > now:
                        continue
                    if state.canonical_status == "ready":
                        continue
                    if (
                        state.detail_status != "ready"
                        and row.media_type_hint != "movie"
                    ):
                        continue
                    due.append((row, state))
                if len(due) >= max(1, limit):
                    break
            return due

    def _count_remaining_stage_rows(
        self,
        session: Session,
        *,
        provider: str,
        stage: str,
        generation: str,
    ) -> int:
        rows = session.exec(
            select(ProviderCatalogTitle).where(
                (ProviderCatalogTitle.provider == provider)
                & (ProviderCatalogTitle.indexed_generation == generation)
            )
        ).all()
        remaining = 0
        for row in rows:
            state = session.get(ProviderTitleIndexState, (provider, row.slug))
            if state is None:
                state = ProviderTitleIndexState(provider=provider, slug=row.slug)
            if stage == "detail_enrichment":
                if state.detail_status != "ready":
                    remaining += 1
                continue
            if state.canonical_status != "ready":
                remaining += 1
        return remaining

    def _load_aliases(self, *, provider: str, slug: str) -> list[str]:
        generation = self._visible_generation(provider)
        if generation is None:
            return []
        with Session(engine) as session:
            rows = session.exec(
                select(ProviderCatalogAlias).where(
                    (ProviderCatalogAlias.provider == provider)
                    & (ProviderCatalogAlias.slug == slug)
                    & (ProviderCatalogAlias.indexed_generation == generation)
                )
            ).all()
        return [row.alias for row in rows]

    def _load_episode_records(self, *, provider: str, slug: str) -> list[EpisodeRecord]:
        generation = self._visible_generation(provider)
        if generation is None:
            return []
        with Session(engine) as session:
            episode_rows = session.exec(
                select(ProviderCatalogEpisode).where(
                    (ProviderCatalogEpisode.provider == provider)
                    & (ProviderCatalogEpisode.slug == slug)
                    & (ProviderCatalogEpisode.indexed_generation == generation)
                )
            ).all()
            language_rows = session.exec(
                select(ProviderEpisodeLanguage).where(
                    (ProviderEpisodeLanguage.provider == provider)
                    & (ProviderEpisodeLanguage.slug == slug)
                    & (ProviderEpisodeLanguage.indexed_generation == generation)
                )
            ).all()
        languages_by_episode: dict[tuple[int, int], list[EpisodeLanguageRecord]] = {}
        for row in language_rows:
            key = (int(row.season), int(row.episode))
            languages_by_episode.setdefault(key, []).append(
                EpisodeLanguageRecord(
                    language=row.language,
                    host_hints=list(row.host_hints or []),
                )
            )
        return [
            EpisodeRecord(
                season=int(row.season),
                episode=int(row.episode),
                relative_path=row.relative_path,
                title_primary=row.title_primary,
                title_secondary=row.title_secondary,
                media_type_hint=row.media_type_hint,
                languages=languages_by_episode.get(
                    (int(row.season), int(row.episode)), []
                ),
            )
            for row in episode_rows
        ]

    def _visible_generation(self, provider: str) -> str | None:
        with Session(engine) as session:
            status = get_provider_index_status(session, provider=provider)
            if status is None:
                return None
            return status.latest_success_generation

    def _count_visible_titles(self, provider: str) -> int:
        generation = self._visible_generation(provider)
        if generation is None:
            return 0
        with Session(engine) as session:
            rows = session.exec(
                select(ProviderCatalogTitle).where(
                    (ProviderCatalogTitle.provider == provider)
                    & (ProviderCatalogTitle.indexed_generation == generation)
                )
            ).all()
        return len(rows)

    def _refresh_interval_hours(self, provider: str) -> float:
        return float(
            CATALOG_SITE_CONFIGS.get(provider, {}).get(
                "provider_index_refresh_hours", 24.0
            )
        )

    def _provider_concurrency(self, provider: str) -> int:
        return max(
            1,
            int(
                CATALOG_SITE_CONFIGS.get(provider, {}).get(
                    "provider_index_concurrency", 1
                )
            ),
        )

    def _enqueue_title_record(
        self,
        provider: str,
        queue: Queue[TitleRecord | object],
        record: TitleRecord,
        writer_failure: list[BaseException],
    ) -> None:
        last_backpressure_log = 0.0
        while True:
            if writer_failure:
                raise RuntimeError(str(writer_failure[0]))
            try:
                queue.put(record, timeout=1.0)
                self._set_progress(provider, queue_depth=queue.qsize())
                return
            except Exception:
                depth = queue.qsize()
                self._set_progress(provider, queue_depth=depth)
                now = monotonic()
                if (
                    now - last_backpressure_log
                    >= PROVIDER_INDEX_BACKPRESSURE_LOG_SECONDS
                ):
                    logger.warning(
                        "Provider catalog {}: writer backpressure queue_depth={} lag_titles={}",
                        provider,
                        depth,
                        self._get_writer_lag(provider),
                    )
                    last_backpressure_log = now

    def _stale_generation(self, status) -> str | None:
        current_generation = getattr(status, "current_generation", None)
        latest_success_generation = getattr(status, "latest_success_generation", None)
        if not current_generation:
            return None
        if status.status == "running":
            return current_generation
        if current_generation != latest_success_generation:
            return current_generation
        return None

    def _set_progress(
        self,
        provider: str,
        *,
        phase: str | None = None,
        stage: str | None = None,
        crawled_titles: int | None = None,
        persisted_titles: int | None = None,
        failed_titles: int | None = None,
        total_titles: int | None | object = _UNSET,
        current_slug: str | None = None,
        queue_depth: int | None = None,
        reset_log_steps: bool = False,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                snapshot = ProviderCatalogProgress(provider=provider)
                self._progress[provider] = snapshot
            if phase is not None:
                snapshot.phase = phase
            if stage is not None:
                snapshot.stage = stage
            if crawled_titles is not None:
                snapshot.crawled_titles = crawled_titles
            if persisted_titles is not None:
                snapshot.persisted_titles = persisted_titles
            if failed_titles is not None:
                snapshot.failed_titles = failed_titles
            if total_titles is not _UNSET:
                snapshot.total_titles = total_titles
            if current_slug is not None:
                snapshot.current_slug = current_slug
            if queue_depth is not None:
                snapshot.queue_depth = queue_depth
            if reset_log_steps:
                snapshot.last_logged_crawl_step = -1
                snapshot.last_logged_persist_step = -1

    def _advance_crawl_progress(
        self,
        provider: str,
        *,
        current_slug: str,
        queue_depth: int,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.setdefault(
                provider, ProviderCatalogProgress(provider=provider)
            )
            snapshot.crawled_titles += 1
            snapshot.current_slug = current_slug
            snapshot.queue_depth = queue_depth
            self._maybe_log_progress(snapshot, kind="crawl")

    def _advance_failed_progress(
        self,
        provider: str,
        *,
        current_slug: str,
        queue_depth: int,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.setdefault(
                provider, ProviderCatalogProgress(provider=provider)
            )
            snapshot.failed_titles += 1
            snapshot.current_slug = current_slug
            snapshot.queue_depth = queue_depth
            self._maybe_log_progress(snapshot, kind="crawl")

    def _advance_persist_progress(
        self,
        provider: str,
        *,
        current_slug: str,
        count: int,
        queue_depth: int,
    ) -> None:
        with self._progress_lock:
            snapshot = self._progress.setdefault(
                provider, ProviderCatalogProgress(provider=provider)
            )
            snapshot.persisted_titles += count
            snapshot.current_slug = current_slug
            snapshot.queue_depth = queue_depth
            self._maybe_log_progress(snapshot, kind="persist")

    def _maybe_log_progress(
        self, snapshot: ProviderCatalogProgress, *, kind: str
    ) -> None:
        percent = (
            snapshot.crawl_percent if kind == "crawl" else snapshot.progress_percent
        )
        if percent is None:
            return
        step = int(percent // PROGRESS_STEP_PERCENT)
        if kind == "crawl":
            if step <= snapshot.last_logged_crawl_step:
                return
            snapshot.last_logged_crawl_step = step
        else:
            if step <= snapshot.last_logged_persist_step:
                return
            snapshot.last_logged_persist_step = step

    def _get_total_titles(self, provider: str) -> int | None:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            return snapshot.total_titles if snapshot is not None else None

    def _get_persisted_titles(self, provider: str) -> int:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                return 0
            return snapshot.persisted_titles

    def _get_failed_titles(self, provider: str) -> int:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                return 0
            return snapshot.failed_titles

    def _get_writer_lag(self, provider: str) -> int:
        with self._progress_lock:
            snapshot = self._progress.get(provider)
            if snapshot is None:
                return 0
            return snapshot.writer_lag_titles

    def _is_bootstrap_ready(self) -> bool:
        with Session(engine) as session:
            return is_catalog_bootstrap_ready(session, providers=CATALOG_SITES_LIST)

    def _log_bootstrap_state(self) -> None:
        with Session(engine) as session:
            statuses = list_provider_index_statuses(session)
        for status in statuses:
            logger.info(
                "Provider catalog bootstrap state: provider={} status={} active_stage={} title_index_status={} detail_status={} canonical_status={} latest_success_generation={} next_refresh_after={}",
                status.provider,
                status.status,
                status.active_stage,
                status.title_index_status,
                status.detail_enrichment_status,
                status.canonical_enrichment_status,
                status.latest_success_generation,
                (
                    status.next_refresh_after.isoformat()
                    if status.next_refresh_after is not None
                    else None
                ),
            )
